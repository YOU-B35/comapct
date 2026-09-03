package com.crosshub.amazon.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record ZiniaoBindRequest(List<StoreCandidate> stores) {
    public record StoreCandidate(
            @JsonProperty("browser_id") String browserId,
            @JsonProperty("browser_oauth") String browserOauth,
            @JsonProperty("ziniao_store_id") String ziniaoStoreId,
            @JsonProperty("browser_name") String browserName,
            @JsonProperty("platform_name") String platformName,
            @JsonProperty("store_username") String storeUsername,
            @JsonProperty("browser_ip") String browserIp
    ) {}
}
