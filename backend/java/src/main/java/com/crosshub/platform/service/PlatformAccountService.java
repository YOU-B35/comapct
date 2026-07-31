package com.crosshub.platform.service;

import com.crosshub.platform.dto.StorePayload;

import java.util.List;
import java.util.Map;

public interface PlatformAccountService {
    List<Map<String, Object>> list(String platform);

    Map<String, Object> upsert(StorePayload payload);

    /** Agent/Helper：按指定租户绑定（不依赖 JWT AuthContext）。allowEmptyPassword=true 时密码可空（浏览器登录场景）。 */
    Map<String, Object> upsertForTenant(Long tenantId, StorePayload payload, boolean allowEmptyPassword);

    List<Map<String, Object>> upsertBatch(String companyName, List<StorePayload> stores);

    Map<String, Object> delete(String id);

    /** Agent/Helper：按指定租户解绑。 */
    Map<String, Object> deleteForTenant(Long tenantId, String id);

    /** 爬虫同步成功后，将未关联的 Temu 绑定账号与 temu_shop 自动匹配 */
    int autoLinkTemuShops(Long tenantId);
}
