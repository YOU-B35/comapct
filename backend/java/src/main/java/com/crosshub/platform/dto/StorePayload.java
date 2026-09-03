package com.crosshub.platform.dto;

public record StorePayload(
        String id,
        String platform,
        String storeName,
        String account,
        String password,
        String companyName,
        String externalShopId,
        String integrationMode,
        String ziniaoBrowserOauth,
        String ziniaoCliStoreId
) {
    public StorePayload(String id, String platform, String storeName, String account, String password, String companyName) {
        this(id, platform, storeName, account, password, companyName, null, null, null, null);
    }

    public StorePayload(
            String id,
            String platform,
            String storeName,
            String account,
            String password,
            String companyName,
            String externalShopId
    ) {
        this(id, platform, storeName, account, password, companyName, externalShopId, null, null, null);
    }
}
