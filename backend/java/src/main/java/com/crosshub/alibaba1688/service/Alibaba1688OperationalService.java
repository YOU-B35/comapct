package com.crosshub.alibaba1688.service;

import java.util.Map;

public interface Alibaba1688OperationalService {
    Map<String, Object> getOperational(Long tenantId, String storeIdOrNull);

    void rebuildAlertsAndStats(Long tenantId);
}
