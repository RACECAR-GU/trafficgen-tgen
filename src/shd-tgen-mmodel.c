/*
 * See LICENSE for licensing information
 */

#include <igraph.h>

#include "shd-tgen.h"

struct _TGenMModel {
    const gchar* fileName;
    igraph_t *graph;
    igraph_integer_t start_vert_id;
    gint refcount;
    guint magic;
};

/** In the given MModel, find the vertex with the given action name.
 * Returns the igraph id of the vertex if finds, else -1. */
static igraph_integer_t
_tgenmmodel_find_vertex(TGenMModel *mmodel, const gchar *action)
{
    TGEN_ASSERT(mmodel);
    g_assert(mmodel->graph);
    igraph_t *graph = mmodel->graph;
    igraph_vit_t vert_iter;
    igraph_integer_t return_value = -1;
    gint res;
    res = igraph_vit_create(graph, igraph_vss_all(), &vert_iter);
    if (res != IGRAPH_SUCCESS) {
        goto done;
    }
    while (!IGRAPH_VIT_END(vert_iter)) {
        igraph_integer_t idx = IGRAPH_VIT_GET(vert_iter);
        const gchar *action_str = VAS(graph, "action", idx);
        tgen_debug("%s", action_str);
        if (g_ascii_strncasecmp(action_str, action, strlen(action)) == 0) {
            return_value = idx;
            goto done;
        }
        IGRAPH_VIT_NEXT(vert_iter);
    }
    goto done;
done:
    igraph_vit_destroy(&vert_iter);
    return return_value;
}

/** Given a MModel with a fileName, flesh out its struct by reading in the
 * graphml and setting its start_vert_id. */
static gboolean
_tgenmmodel_load_mmodel(TGenMModel *mmodel)
{
    TGEN_ASSERT(mmodel);
    g_assert(mmodel->fileName);
    tgen_debug("Opening MModel graph file '%s'", mmodel->fileName);
    FILE *file = fopen(mmodel->fileName, "r");
    if (!file) {
        tgen_critical("fopen returned NULL, problem opening MModel graph file "
                "path '%s'", mmodel->fileName);
        return FALSE;
    }
    mmodel->graph = g_new0(igraph_t, 1);
    gint result = igraph_read_graph_graphml(mmodel->graph, file, 0);
    fclose(file);
    if (result != IGRAPH_SUCCESS) {
        tgen_critical("error reading igraph from MModel file");
        g_free(mmodel->graph);
        return FALSE;
    }
    mmodel->start_vert_id = _tgenmmodel_find_vertex(mmodel, "start");
    if (mmodel->start_vert_id < 0) {
        tgen_critical("no start vertex found in MModel file");
        g_free(mmodel->graph);
        return FALSE;
    }
    return TRUE;
}

TGenMModel *
tgenmmodel_new(const gchar *mmodelPath)
{
    TGenMModel *mmodel = g_new0(TGenMModel, 1);
    mmodel->magic = TGEN_MAGIC;
    mmodel->refcount = 1;
    mmodel->fileName = mmodelPath;
    if (!_tgenmmodel_load_mmodel(mmodel)) {
        tgenmmodel_unref(mmodel);
        return NULL;
    }
    return mmodel;
}

/** Helper struct for _tgenmmodel_selectNextVertex. In that func we are sitting
 * on a specific vertex and need to tie together the ID of an adjacent vertex
 * with the weight of the edge between them. */
struct VertAndWeight {
    igraph_integer_t v;
    double w;
};

static igraph_integer_t
_tgenmmodel_selectNextVertex(TGenMModel *mmodel, igraph_integer_t current_vert_id)
{
    igraph_vs_t vs; // vertex selector
    igraph_vit_t vit; // vertex iterator
    /* These are DIFFERENT negative values just for debugging purposes */
    igraph_integer_t selected_vert_id = -1;
    igraph_integer_t working_vert_id = -2;
    igraph_integer_t working_edge_id = -3;
    struct VertAndWeight vw;
    igraph_real_t working_edge_weight;
    igraph_real_t cumulative_weight = 0;
    gdouble rand_value;
    GArray *adj_verts = g_array_new(TRUE, FALSE, sizeof(struct VertAndWeight));
    gint res, i;

    /* Get all vertexes adjacent to the current_vert_id */
    res = igraph_vs_adj(&vs, current_vert_id, IGRAPH_OUT);
    if (res != IGRAPH_SUCCESS) {
        tgen_critical("unable to create adj vertex selector");
        goto done;
    }
    res = igraph_vit_create(mmodel->graph, vs, &vit);
    if (res != IGRAPH_SUCCESS) {
        tgen_critical("unable to create adj vertex iterator");
        goto done;
    }

    /* Iterate over them and pair each adj vert with the edge weight between
     * the current vert and it. We also accumulate a cumulative weight for use
     * later */
    while (!IGRAPH_VIT_END(vit)) {
        working_vert_id = IGRAPH_VIT_GET(vit);
        /* Get the edge between the current_vert_id and the working_vert_id */
        res = igraph_get_eid(mmodel->graph, &working_edge_id,
                current_vert_id, working_vert_id, TRUE, TRUE);
        if (res != IGRAPH_SUCCESS) {
            tgen_critical("unable to find edge between %s and %s",
                    VAS(mmodel->graph, "id", current_vert_id),
                    VAS(mmodel->graph, "id", working_vert_id));
            goto done;
        }
        /* Get the weight from the edge */
        working_edge_weight = EAN(mmodel->graph, "weight", working_edge_id);
        /* Add it the sum of weights of all edges */
        cumulative_weight += working_edge_weight;
        /* And store the working_vert_id and its weight in the list of adjacent
         * verts */
        vw.v = working_vert_id; vw.w = working_edge_weight;
        g_array_append_val(adj_verts, vw);
        //tgen_debug("%s (%d) to %s (%d) via edge %d: weight is %f and total is %f",
        //        VAS(mmodel->graph, "id", current_vert_id), current_vert_id,
        //        VAS(mmodel->graph, "id", working_vert_id), working_vert_id,
        //        working_edge_id, working_edge_weight, cumulative_weight);
        IGRAPH_VIT_NEXT(vit);
    }
    /* We now know all the possible next verts, their weight of the edges to
     * each of them, and the total weight. Pick a positive random number below
     * the total weight. Iterate through the list of adj verts and subtract
     * their wegiths from the random value. Stop and return the first vert
     * that would make random value go negative. This is a simple way to make a
     * weighted random choice */
    rand_value = g_random_double_range(0, cumulative_weight);
    for (i = 0; i < adj_verts->len; i++) {
        vw = g_array_index(adj_verts, struct VertAndWeight, i);
        if (rand_value < vw.w) {
            selected_vert_id = vw.v;
            goto done;
        }
        rand_value -= vw.w;
    }
    goto done;

done:
    igraph_vit_destroy(&vit);
    igraph_vs_destroy(&vs);
    g_array_unref(adj_verts);
    return selected_vert_id;
}

/** Ask the MModel to generate a path. Stores the instructions for us (the
 * local client) in ourStr and the instructions for them (the remote server) in
 * theirStr. Returns TRUE if we were successful, else FALSE */
gboolean
tgenmmodel_generatePath(TGenMModel *mmodel, GString *ourStr, GString *theirStr)
{
    TGEN_ASSERT(mmodel);
    g_assert(mmodel->graph);
    igraph_t *graph = mmodel->graph;

    igraph_integer_t current_vert_id = mmodel->start_vert_id;
    igraph_integer_t working_vert_id;
    igraph_integer_t working_edge_id;
    gchar *working_vert_action;
    igraph_real_t delay;
    igraph_real_t our_cum_delay = 0;
    igraph_real_t their_cum_delay = 0;
    gsize bytes_we_will_send = 0;
    gsize bytes_they_will_send = 0;
    gboolean direction_in = TRUE;
    gboolean is_their_first_item = TRUE;
    gboolean is_our_first_item = TRUE;
    gint res;
    while (TRUE) {
        working_vert_id = _tgenmmodel_selectNextVertex(mmodel, current_vert_id);
        if (working_vert_id < 0) {
            tgen_critical("We should have gotten another vertex from "
                    "_tgenmmodel_selectNextVertex but didn't. Giving up.");
            return FALSE;
        }
        working_vert_action = VAS(mmodel->graph, "action", working_vert_id);
        if (g_ascii_strcasecmp(working_vert_action, "stop") == 0) {
            tgen_debug("Stopping as we hit a stop vertex");
            break;
        }
        res = igraph_get_eid(mmodel->graph, &working_edge_id, current_vert_id,
                working_vert_id, TRUE, TRUE);
        if (res != IGRAPH_SUCCESS) {
            tgen_critical("Couldn't find edge between %s and %s",
                    VAS(mmodel->graph, "id", current_vert_id),
                    VAS(mmodel->graph, "id", working_vert_id));
            return FALSE;
        }
        delay = EAN(mmodel->graph, "delay", working_edge_id);
        if (g_ascii_strcasecmp(working_vert_action, "packet_in") == 0) {
            direction_in = TRUE;
        } else if (g_ascii_strcasecmp(working_vert_action, "packet_out") == 0) {
            direction_in = FALSE;
        } else {
            tgen_critical("Unknown vertex action %s", working_vert_action);
            return FALSE;
        }
        our_cum_delay += delay;
        their_cum_delay += delay;
        if (direction_in) {
            tgen_debug("Telling them to send packet after %f", their_cum_delay);
            g_string_append_printf(theirStr, "%s%d",
                    is_their_first_item?"":",", (int)their_cum_delay);
            is_their_first_item = FALSE;
            their_cum_delay = 0;
            bytes_they_will_send += TGEN_MMODEL_PACKET_DATA_SIZE;
        } else {
            tgen_debug("Telling us to send packet after %f", our_cum_delay);
            g_string_append_printf(ourStr, "%s%d",
                    is_our_first_item?"":",", (int)our_cum_delay);
            is_our_first_item = FALSE;
            our_cum_delay = 0;
            bytes_we_will_send += TGEN_MMODEL_PACKET_DATA_SIZE;
        }
        //tgen_debug("Moving from %s to %s",
        //        VAS(mmodel->graph, "id", current_vert_id),
        //        VAS(mmodel->graph, "id", working_vert_id));
        current_vert_id = working_vert_id;
    }
    GString *bytes = g_string_new(NULL);
    g_string_append_printf(bytes, "%d,", (int)bytes_we_will_send);
    g_string_prepend(theirStr, bytes->str);
    g_string_free(bytes, TRUE);

    bytes = g_string_new(NULL);
    g_string_append_printf(bytes, "%d,", (int)bytes_they_will_send);
    g_string_prepend(ourStr, bytes->str);
    g_string_free(bytes, TRUE);
    return TRUE;

}

static void _tgenmmodel_free(TGenMModel *mmodel)
{
    TGEN_ASSERT(mmodel);
    g_assert(mmodel->refcount == 0);
    g_free(mmodel->graph);
    g_free(mmodel);
}

void tgenmmodel_ref(TGenMModel *mmodel)
{
    TGEN_ASSERT(mmodel);
    //tgen_debug("TGenMModel ref++");
    mmodel->refcount++;
}

void tgenmmodel_unref(TGenMModel *mmodel)
{
    TGEN_ASSERT(mmodel);
    //tgen_debug("TGenMModel ref--");
    if (--(mmodel->refcount) == 0) {
        _tgenmmodel_free(mmodel);
    }
}