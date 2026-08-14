package com.crosshub.douyin.service;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class CompassRankTrackAnalyzerTest {

    private static Map<String, Object> item(
            String id,
            int rank,
            Double payAmt,
            Double payCnt,
            Double click,
            Double show,
            Double cvr
    ) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("productId", id);
        m.put("rankNo", rank);
        m.put("payAmt", payAmt);
        m.put("payCnt", payCnt);
        m.put("dealCnt", payCnt);
        m.put("clickCnt", click);
        m.put("showCnt", show);
        m.put("clickPayCvr", cvr);
        m.put("orderCnt", payCnt);
        m.put("reportDay", "2026-08-14");
        return m;
    }

    @Test
    void peerWindow_flipsTodayYesterday() {
        assertEquals("yesterday", CompassRankTrackAnalyzer.peerWindow("today"));
        assertEquals("today", CompassRankTrackAnalyzer.peerWindow("yesterday"));
    }

    @Test
    void peerUnavailable_marksAllDataInsufficient() {
        List<Map<String, Object>> cur = new ArrayList<>();
        cur.add(item("p1", 1, 100.0, 10.0, 50.0, 200.0, 2.0));
        CompassRankTrackAnalyzer.enrich(cur, List.of(), false);
        assertNull(cur.get(0).get("trackScore"));
        assertEquals("数据不足", cur.get(0).get("trackLabel"));
        assertEquals(false, cur.get(0).get("isNewEntry"));
        assertNull(cur.get(0).get("rankDelta"));
    }

    @Test
    void risingRank_andSales_suggestsTrack() {
        List<Map<String, Object>> cur = new ArrayList<>();
        cur.add(item("p1", 5, 200.0, 20.0, 100.0, 400.0, 3.0));
        List<Map<String, Object>> peer = List.of(item("p1", 40, 100.0, 10.0, 50.0, 200.0, 2.0));
        CompassRankTrackAnalyzer.enrich(cur, peer, true);
        Map<String, Object> row = cur.get(0);
        assertEquals(35, row.get("rankDelta"));
        assertEquals(false, row.get("isNewEntry"));
        assertEquals(1.0, (Double) row.get("payAmtDeltaPct"), 1e-6);
        int score = (Integer) row.get("trackScore");
        assertTrue(score >= 70, "score=" + score);
        assertEquals("建议追踪", row.get("trackLabel"));
        assertNotNull(row.get("peerMetrics"));
        assertFalse(((List<?>) row.get("trackReasons")).isEmpty());
    }

    @Test
    void newEntry_top50_notDataInsufficient() {
        List<Map<String, Object>> cur = new ArrayList<>();
        cur.add(item("new1", 12, 50.0, 5.0, 20.0, 80.0, 1.0));
        List<Map<String, Object>> peer = List.of(item("other", 1, 9.0, 1.0, 1.0, 1.0, 1.0));
        CompassRankTrackAnalyzer.enrich(cur, peer, true);
        assertEquals(true, cur.get(0).get("isNewEntry"));
        List<?> reasons = (List<?>) cur.get(0).get("trackReasons");
        assertTrue(reasons.stream().anyMatch(r -> String.valueOf(r).contains("新进")));
        assertNotEquals("数据不足", cur.get(0).get("trackLabel"));
        assertNotNull(cur.get(0).get("trackScore"));
    }

    @Test
    void fallingWeak_notRecommended() {
        List<Map<String, Object>> cur = new ArrayList<>();
        cur.add(item("p1", 80, 50.0, 5.0, 10.0, 40.0, 0.5));
        List<Map<String, Object>> peer = List.of(item("p1", 20, 100.0, 15.0, 40.0, 100.0, 2.0));
        CompassRankTrackAnalyzer.enrich(cur, peer, true);
        assertEquals(-60, cur.get(0).get("rankDelta"));
        assertTrue((Integer) cur.get(0).get("trackScore") < 40);
        assertEquals("暂不建议", cur.get(0).get("trackLabel"));
    }
}
