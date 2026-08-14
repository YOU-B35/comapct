package com.crosshub.douyin.service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Pure analyzer: today/yesterday compass product-rank track scoring (spec v1).
 */
public final class CompassRankTrackAnalyzer {
    private CompassRankTrackAnalyzer() {}

    public static String peerWindow(String dateWindow) {
        String v = dateWindow == null ? "" : dateWindow.trim().toLowerCase(Locale.ROOT);
        return "yesterday".equals(v) ? "today" : "yesterday";
    }

    public static void enrich(
            List<Map<String, Object>> currentItems,
            List<Map<String, Object>> peerItems,
            boolean peerAvailable
    ) {
        if (currentItems == null || currentItems.isEmpty()) {
            return;
        }
        Map<String, Map<String, Object>> peerById = new HashMap<>();
        if (peerItems != null) {
            for (Map<String, Object> p : peerItems) {
                if (p == null) {
                    continue;
                }
                String id = str(p.get("productId"));
                if (!id.isBlank()) {
                    peerById.put(id, p);
                }
            }
        }
        double payAmtP80 = percentileThreshold(currentItems, "payAmt", 0.80);
        double payCntP80 = percentileThreshold(currentItems, "payCnt", 0.80);

        for (Map<String, Object> cur : currentItems) {
            if (cur == null) {
                continue;
            }
            if (!peerAvailable) {
                putInsufficient(cur);
                continue;
            }
            String id = str(cur.get("productId"));
            Map<String, Object> peer = peerById.get(id);
            boolean isNew = peer == null;
            cur.put("isNewEntry", isNew);

            Integer curRank = intOrNull(cur.get("rankNo"));
            Integer peerRank = peer == null ? null : intOrNull(peer.get("rankNo"));
            cur.put("peerRankNo", peerRank);
            Integer rankDelta = (peerRank != null && curRank != null) ? (peerRank - curRank) : null;
            cur.put("rankDelta", rankDelta);

            Double payAmtDeltaPct = isNew ? null : pctDelta(num(cur.get("payAmt")), num(peer.get("payAmt")));
            Double payCntCur = firstNum(cur.get("payCnt"), cur.get("dealCnt"));
            Double payCntPeer = peer == null ? null : firstNum(peer.get("payCnt"), peer.get("dealCnt"));
            Double payCntDeltaPct = isNew ? null : pctDelta(payCntCur, payCntPeer);
            Double clickDelta = isNew ? null : pctDelta(num(cur.get("clickCnt")), num(peer.get("clickCnt")));
            Double showDelta = isNew ? null : pctDelta(num(cur.get("showCnt")), num(peer.get("showCnt")));
            Double cvrDelta = isNew ? null : ppDelta(num(cur.get("clickPayCvr")), num(peer.get("clickPayCvr")));

            cur.put("payAmtDeltaPct", payAmtDeltaPct);
            cur.put("payCntDeltaPct", payCntDeltaPct);
            cur.put("clickCntDeltaPct", clickDelta);
            cur.put("showCntDeltaPct", showDelta);
            cur.put("clickPayCvrDelta", cvrDelta);
            cur.put("peerMetrics", peer == null ? null : snapshot(peer));

            double sRank = scoreRank(isNew, curRank, rankDelta);
            double sSales = scoreSales(
                    payAmtDeltaPct,
                    payCntDeltaPct,
                    num(cur.get("payAmt")),
                    payCntCur,
                    payAmtP80,
                    payCntP80
            );
            double sTraffic = scoreTraffic(clickDelta, showDelta, cvrDelta);
            int trackScore = (int) Math.round(0.40 * sRank + 0.35 * sSales + 0.25 * sTraffic);
            trackScore = Math.max(0, Math.min(100, trackScore));
            String label = labelOf(trackScore);
            cur.put("trackScore", trackScore);
            cur.put("trackLabel", label);
            cur.put(
                    "trackReasons",
                    buildReasons(isNew, curRank, rankDelta, payAmtDeltaPct, payCntDeltaPct, clickDelta, cvrDelta)
            );
            cur.put("watchHint", watchHint(label));
            cur.put("followHint", followHint(label));
        }
    }

    private static void putInsufficient(Map<String, Object> cur) {
        // Whole peer window missing — not a new-entry signal; UI shows "—" not "新进".
        cur.put("isNewEntry", false);
        cur.put("peerRankNo", null);
        cur.put("rankDelta", null);
        cur.put("payAmtDeltaPct", null);
        cur.put("payCntDeltaPct", null);
        cur.put("clickCntDeltaPct", null);
        cur.put("showCntDeltaPct", null);
        cur.put("clickPayCvrDelta", null);
        cur.put("peerMetrics", null);
        cur.put("trackScore", null);
        cur.put("trackLabel", "数据不足");
        cur.put("trackReasons", List.of());
        cur.put("watchHint", watchHint("数据不足"));
        cur.put("followHint", followHint("数据不足"));
    }

    static double scoreRank(boolean isNew, Integer curRank, Integer rankDelta) {
        if (isNew) {
            int r = curRank == null ? 999 : curRank;
            if (r <= 50) {
                return 90;
            }
            if (r <= 100) {
                return 75;
            }
            return 60;
        }
        if (rankDelta == null) {
            return 40;
        }
        if (rankDelta >= 30) {
            return 95;
        }
        if (rankDelta >= 10) {
            return 80;
        }
        if (rankDelta >= 1) {
            return 65;
        }
        if (rankDelta == 0) {
            return curRank != null && curRank <= 20 ? 70 : 50;
        }
        if (rankDelta >= -10) {
            return 35;
        }
        return 15;
    }

    static double scoreSales(
            Double payAmtDeltaPct,
            Double payCntDeltaPct,
            Double payAmt,
            Double payCnt,
            double payAmtP80,
            double payCntP80
    ) {
        Double maxPct = null;
        if (payAmtDeltaPct != null && payCntDeltaPct != null) {
            maxPct = Math.max(payAmtDeltaPct, payCntDeltaPct);
        } else if (payAmtDeltaPct != null) {
            maxPct = payAmtDeltaPct;
        } else if (payCntDeltaPct != null) {
            maxPct = payCntDeltaPct;
        }
        double base = maxPct == null ? 40 : bandFromPct(maxPct);
        boolean topAbs = (payAmt != null && payAmt >= payAmtP80 && payAmtP80 > 0)
                || (payCnt != null && payCnt >= payCntP80 && payCntP80 > 0);
        boolean risingOrFlat = maxPct != null && maxPct >= 0;
        if (topAbs && risingOrFlat) {
            base = Math.min(100, base + 10);
        }
        return base;
    }

    static double scoreTraffic(Double clickDelta, Double showDelta, Double cvrDelta) {
        Double pct = clickDelta != null ? clickDelta : showDelta;
        double base = pct == null ? 40 : bandFromPct(pct);
        double adj = 0;
        if (cvrDelta != null) {
            if (cvrDelta >= 1) {
                adj = 15;
            } else if (cvrDelta >= 0) {
                adj = 5;
            } else if (cvrDelta < -1) {
                adj = -15;
            }
        }
        return Math.max(0, Math.min(100, base + adj));
    }

    private static double bandFromPct(double pct) {
        if (pct >= 0.50) {
            return 95;
        }
        if (pct >= 0.20) {
            return 80;
        }
        if (pct >= 0.05) {
            return 65;
        }
        if (pct >= -0.05) {
            return 50;
        }
        if (pct >= -0.20) {
            return 30;
        }
        return 15;
    }

    private static String labelOf(int score) {
        if (score >= 70) {
            return "建议追踪";
        }
        if (score >= 40) {
            return "可观望";
        }
        return "暂不建议";
    }

    private static List<String> buildReasons(
            boolean isNew,
            Integer curRank,
            Integer rankDelta,
            Double payAmtDeltaPct,
            Double payCntDeltaPct,
            Double clickDelta,
            Double cvrDelta
    ) {
        List<String> reasons = new ArrayList<>();
        if (isNew) {
            reasons.add("新进榜 Top" + (curRank == null ? "?" : curRank));
        } else if (rankDelta != null) {
            if (rankDelta > 0) {
                reasons.add("排名↑" + rankDelta);
            } else if (rankDelta < 0) {
                reasons.add("排名↓" + Math.abs(rankDelta));
            } else {
                reasons.add("排名持平");
            }
        }
        appendPctReason(reasons, "成交额", payAmtDeltaPct);
        appendPctReason(reasons, "成交件数", payCntDeltaPct);
        appendPctReason(reasons, "点击", clickDelta);
        if (cvrDelta != null) {
            String sign = cvrDelta > 0 ? "+" : "";
            reasons.add("转化率" + sign + String.format(Locale.ROOT, "%.1f", cvrDelta) + "pp");
        }
        if (reasons.size() > 5) {
            return new ArrayList<>(reasons.subList(0, 5));
        }
        return reasons;
    }

    private static void appendPctReason(List<String> reasons, String label, Double pct) {
        if (pct == null || reasons.size() >= 5) {
            return;
        }
        String sign = pct > 0 ? "+" : "";
        reasons.add(label + sign + String.format(Locale.ROOT, "%.0f", pct * 100) + "%");
    }

    private static String watchHint(String label) {
        return switch (label) {
            case "建议追踪" -> "排名或热度动量强，建议加入盯梢名单看后续榜位。";
            case "可观望" -> "有一定变化，可隔日再比一次再决定是否盯梢。";
            case "暂不建议" -> "动量偏弱或下滑，暂不必优先盯梢。";
            default -> "缺少对照窗口数据，请先同步今日与昨日。";
        };
    }

    private static String followHint(String label) {
        return switch (label) {
            case "建议追踪" -> "成交/流量信号偏强，可作为跟卖候选做进一步调研。";
            case "可观望" -> "跟卖价值一般，建议结合类目与供给再判断。";
            case "暂不建议" -> "跟卖优先级低。";
            default -> "无法评估跟卖价值。";
        };
    }

    private static Map<String, Object> snapshot(Map<String, Object> peer) {
        Map<String, Object> snap = new LinkedHashMap<>();
        snap.put("rankNo", peer.get("rankNo"));
        snap.put("payAmt", peer.get("payAmt"));
        snap.put("clickCnt", peer.get("clickCnt"));
        snap.put("payCnt", peer.get("payCnt"));
        snap.put("clickPayCvr", peer.get("clickPayCvr"));
        snap.put("showCnt", peer.get("showCnt"));
        snap.put("orderCnt", peer.get("orderCnt"));
        snap.put("dealCnt", peer.get("dealCnt"));
        snap.put("reportDay", peer.get("reportDay"));
        return snap;
    }

    /** Threshold at given quantile (0..1): value at index floor(n*q) of ascending sort. */
    static double percentileThreshold(List<Map<String, Object>> items, String field, double q) {
        List<Double> vals = new ArrayList<>();
        for (Map<String, Object> item : items) {
            if (item == null) {
                continue;
            }
            Double v = num(item.get(field));
            if (v != null) {
                vals.add(v);
            }
        }
        if (vals.isEmpty()) {
            return 0;
        }
        vals.sort(Double::compareTo);
        int idx = (int) Math.floor(vals.size() * q);
        if (idx >= vals.size()) {
            idx = vals.size() - 1;
        }
        if (idx < 0) {
            idx = 0;
        }
        return vals.get(idx);
    }

    static Double pctDelta(Double cur, Double peer) {
        if (cur == null || peer == null || peer <= 0) {
            return null;
        }
        return (cur - peer) / peer;
    }

    static Double ppDelta(Double cur, Double peer) {
        if (cur == null || peer == null) {
            return null;
        }
        return cur - peer;
    }

    private static Double firstNum(Object a, Object b) {
        Double x = num(a);
        return x != null ? x : num(b);
    }

    private static Double num(Object v) {
        if (v == null) {
            return null;
        }
        if (v instanceof Number n) {
            return n.doubleValue();
        }
        try {
            String s = String.valueOf(v).trim();
            if (s.isEmpty()) {
                return null;
            }
            return Double.parseDouble(s);
        } catch (Exception e) {
            return null;
        }
    }

    private static Integer intOrNull(Object v) {
        if (v == null) {
            return null;
        }
        if (v instanceof Number n) {
            return n.intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(v).trim());
        } catch (Exception e) {
            return null;
        }
    }

    private static String str(Object v) {
        return v == null ? "" : String.valueOf(v).trim();
    }
}
