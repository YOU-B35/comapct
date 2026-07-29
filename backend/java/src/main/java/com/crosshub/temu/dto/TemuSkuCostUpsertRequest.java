package com.crosshub.temu.dto;

import java.util.List;
import java.util.Map;

public record TemuSkuCostUpsertRequest(List<Map<String, Object>> items) {}
