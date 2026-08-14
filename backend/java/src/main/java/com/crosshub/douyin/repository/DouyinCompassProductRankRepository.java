package com.crosshub.douyin.repository;

import com.crosshub.douyin.entity.DouyinCompassProductRank;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface DouyinCompassProductRankRepository extends JpaRepository<DouyinCompassProductRank, String> {
    List<DouyinCompassProductRank> findByTenantIdAndStoreIdAndBoardAndDateWindowOrderByRankNoAsc(
            Long tenantId, String storeId, String board, String dateWindow
    );

    List<DouyinCompassProductRank> findByTenantIdAndBoardAndDateWindowOrderBySyncedAtDescRankNoAsc(
            Long tenantId, String board, String dateWindow
    );

    void deleteByTenantIdAndStoreIdAndBoardAndDateWindow(
            Long tenantId, String storeId, String board, String dateWindow
    );
}
