package com.crosshub.pdd.service;

import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PddWindowDayListTest {

    @Test
    void todayReturnsOnlyCurrentDay() {
        List<String> days = PddOpsService.windowDayList("today");
        assertEquals(List.of(LocalDate.now().toString()), days);
    }

    @Test
    void d90ReturnsNinetyDaysEndingToday() {
        List<String> days = PddOpsService.windowDayList("d90");
        assertEquals(90, days.size());
        assertEquals(LocalDate.now().toString(), days.get(days.size() - 1));
        assertTrue(days.get(0).compareTo(days.get(days.size() - 1)) < 0);
    }

    @Test
    void unknownWindowFallsBackToToday() {
        List<String> days = PddOpsService.windowDayList("all");
        assertEquals(1, days.size());
    }
}
