package com.crosshub.amazon.service.impl;

import com.crosshub.amazon.entity.AmazonSyncJob;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

import static org.junit.jupiter.api.Assertions.assertFalse;

class AmazonSyncServiceImplTtlTest {

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    @Test
    void runningAmazonSyncJobStartedTwentyMinutesAgoIsNotStale() {
        AmazonSyncServiceImpl service = new AmazonSyncServiceImpl(
                null, null, null, null, null, null, null, null
        );

        AmazonSyncJob job = new AmazonSyncJob();
        job.setStatus("running");
        job.setStartedAt(LocalDateTime.now().minusMinutes(20).format(TS));

        assertFalse(service.isStale(job));
    }
}
