package com.crosshub.alibaba1688.service;

import com.crosshub.agent.service.AgentPresenceService;
import com.crosshub.alibaba1688.entity.Alibaba1688Product;
import com.crosshub.alibaba1688.entity.Alibaba1688ProductCategory;
import com.crosshub.alibaba1688.repository.Alibaba1688ProductCategoryRepository;
import com.crosshub.alibaba1688.repository.Alibaba1688ProductRepository;
import com.crosshub.security.AuthContext;
import com.crosshub.tenant.service.DataScopeService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class Alibaba1688ProductServiceTest {
    @Test
    void mergesTagsWithOr() {
        // existing potential=1,yanxuan=0 + incoming potential=0,yanxuan=1 => both 1
        assertEquals(1, Alibaba1688ProductService.orMergeTag(1, 0));
        assertEquals(1, Alibaba1688ProductService.orMergeTag(0, 1));
        assertEquals(1, Alibaba1688ProductService.orMergeTag(1, 1));
        assertEquals(0, Alibaba1688ProductService.orMergeTag(0, 0));
        assertEquals(1, Alibaba1688ProductService.orMergeTag(null, 1));
        assertEquals(0, Alibaba1688ProductService.orMergeTag(null, null));
    }

    @Test
    void blankIndexScoreDoesNotWipeExisting() {
        assertEquals("4.1", Alibaba1688ProductService.mergeIndexScore("4.1", ""));
        assertEquals("4.1", Alibaba1688ProductService.mergeIndexScore("4.1", "  "));
        assertEquals("4.1", Alibaba1688ProductService.mergeIndexScore("4.1", null));
        assertEquals("3.8", Alibaba1688ProductService.mergeIndexScore("4.1", "3.8"));
        assertEquals("2.0", Alibaba1688ProductService.mergeIndexScore(null, "2.0"));
        assertEquals(null, Alibaba1688ProductService.mergeIndexScore(null, ""));
    }

    @Test
    void incomingStatusWinsSoSyncCanCorrectWrongBucket() {
        assertEquals("sold_out", Alibaba1688ProductService.mergeProductStatus("on_sale", "sold_out"));
        assertEquals("pending_list", Alibaba1688ProductService.mergeProductStatus("on_sale", "pending_list"));
        assertEquals("on_sale", Alibaba1688ProductService.mergeProductStatus("sold_out", "on_sale"));
        assertEquals("on_sale", Alibaba1688ProductService.mergeProductStatus("", "on_sale"));
        assertEquals("draft", Alibaba1688ProductService.mergeProductStatus("draft", ""));
    }

    @Test
    void ingestMapsGmv1dOntoListDto() {
        List<Alibaba1688Product> store = new ArrayList<>();
        Alibaba1688ProductRepository productRepository = mock(Alibaba1688ProductRepository.class);
        DataScopeService dataScopeService = mock(DataScopeService.class);
        when(dataScopeService.requireTenantId()).thenReturn(1L);
        when(productRepository.findByTenantIdAndStoreIdAndOfferId(anyLong(), anyString(), anyString()))
                .thenAnswer(inv -> store.stream()
                        .filter(row -> inv.getArgument(0).equals(row.getTenantId())
                                && inv.getArgument(1).equals(row.getStoreId())
                                && inv.getArgument(2).equals(row.getOfferId()))
                        .findFirst());
        when(productRepository.save(any(Alibaba1688Product.class))).thenAnswer(inv -> {
            Alibaba1688Product row = inv.getArgument(0);
            store.removeIf(existing -> existing.getId() != null && existing.getId().equals(row.getId()));
            store.add(row);
            return row;
        });
        when(productRepository.findByTenantIdOrderBySyncedAtDesc(1L)).thenAnswer(inv -> List.copyOf(store));

        Alibaba1688ProductService service = new Alibaba1688ProductService(
                dataScopeService,
                new AuthContext(),
                mock(AgentPresenceService.class),
                mock(Alibaba1688SessionService.class),
                productRepository,
                mock(Alibaba1688ProductCategoryRepository.class),
                mock(JdbcTemplate.class),
                new ObjectMapper(),
                new Alibaba1688StoreKeyResolver(mock(JdbcTemplate.class), new ObjectMapper())
        );

        Map<String, Object> product = new LinkedHashMap<>();
        product.put("offer_id", "offer-gmv1d");
        product.put("gmv_1d", "妤?8.00");
        Map<String, Object> ingested = service.ingestProducts(1L, Map.of("products", List.of(product)));
        assertEquals(1, ingested.get("ingested"));

        Map<String, Object> listed = service.listProducts("all", "all", null);
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> items = (List<Map<String, Object>>) listed.get("items");
        assertFalse(items.isEmpty());
        assertEquals("妤?8.00", items.get(0).get("gmv1d"));
    }

    @Test
    void ingestPersistsPriceAndImageUrl() {
        List<Alibaba1688Product> store = new ArrayList<>();
        Alibaba1688ProductRepository productRepository = mock(Alibaba1688ProductRepository.class);
        DataScopeService dataScopeService = mock(DataScopeService.class);
        when(dataScopeService.requireTenantId()).thenReturn(1L);
        when(productRepository.findByTenantIdAndStoreIdAndOfferId(anyLong(), anyString(), anyString()))
                .thenAnswer(inv -> store.stream()
                        .filter(row -> inv.getArgument(0).equals(row.getTenantId())
                                && inv.getArgument(1).equals(row.getStoreId())
                                && inv.getArgument(2).equals(row.getOfferId()))
                        .findFirst());
        when(productRepository.save(any(Alibaba1688Product.class))).thenAnswer(inv -> {
            Alibaba1688Product row = inv.getArgument(0);
            store.removeIf(existing -> existing.getId() != null && existing.getId().equals(row.getId()));
            store.add(row);
            return row;
        });
        when(productRepository.findByTenantIdOrderBySyncedAtDesc(1L)).thenAnswer(inv -> List.copyOf(store));

        Alibaba1688ProductService service = new Alibaba1688ProductService(
                dataScopeService,
                new AuthContext(),
                mock(AgentPresenceService.class),
                mock(Alibaba1688SessionService.class),
                productRepository,
                mock(Alibaba1688ProductCategoryRepository.class),
                mock(JdbcTemplate.class),
                new ObjectMapper(),
                new Alibaba1688StoreKeyResolver(mock(JdbcTemplate.class), new ObjectMapper())
        );

        Map<String, Object> product = new LinkedHashMap<>();
        product.put("offer_id", "offer-price");
        product.put("price", "0.17~0.18");
        product.put("image_url", "https://cbu01.alicdn.com/img/ibank/demo.jpg");
        product.put("status", "pending_list");
        service.ingestProducts(1L, Map.of("products", List.of(product)));

        Map<String, Object> listed = service.listProducts("all", "all", null);
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> items = (List<Map<String, Object>>) listed.get("items");
        assertEquals("0.17~0.18", items.get(0).get("price"));
        assertEquals("https://cbu01.alicdn.com/img/ibank/demo.jpg", items.get(0).get("imageUrl"));
        assertEquals("pending_list", items.get(0).get("status"));
    }

    @Test
    void successfulCategoryReplaceRemovesOnlyMissingMembers() {
        Alibaba1688ProductCategoryRepository categoryRepository = mock(Alibaba1688ProductCategoryRepository.class);
        Alibaba1688ProductCategory existingA = category("row-a", "offer-a", "growth_potential");
        Alibaba1688ProductCategory existingB = category("row-b", "offer-b", "growth_potential");
        when(categoryRepository.findByTenantIdAndStoreIdAndCategoryCode(1L, "store-1", "growth_potential"))
                .thenReturn(List.of(existingA, existingB));

        Alibaba1688ProductService service = serviceWith(
                mock(Alibaba1688ProductRepository.class),
                categoryRepository
        );
        service.replaceCategory(1L, "store-1", "growth_potential", List.of("offer-b", "offer-c"), "sync-2");

        verify(categoryRepository).deleteAll(List.of(existingA));
        verify(categoryRepository).saveAll(org.mockito.ArgumentMatchers.argThat(rows -> {
            List<Alibaba1688ProductCategory> saved = new ArrayList<>();
            rows.forEach(saved::add);
            return saved.size() == 2
                    && saved.stream().map(Alibaba1688ProductCategory::getOfferId).sorted().toList()
                    .equals(List.of("offer-b", "offer-c"));
        }));
    }

    @Test
    void categoryFailureDoesNotClearPreviousRelations() {
        Alibaba1688ProductCategoryRepository categoryRepository = mock(Alibaba1688ProductCategoryRepository.class);
        Alibaba1688ProductService service = serviceWith(
                mock(Alibaba1688ProductRepository.class),
                categoryRepository
        );

        service.ingestProducts(1L, Map.of(
                "store_id", "store-1",
                "products", List.of(),
                "categories", Map.of(
                        "growth_potential", Map.of("status", "failed", "error_code", "A1688_CATEGORY_INVALID")
                )
        ));

        verify(categoryRepository, never()).deleteAll(any());
        verify(categoryRepository, never()).saveAll(any());
    }

    @Test
    void listPotentialUsesCategoryRelationNotLegacyBooleanFlag() {
        Alibaba1688ProductRepository productRepository = mock(Alibaba1688ProductRepository.class);
        Alibaba1688ProductCategoryRepository categoryRepository = mock(Alibaba1688ProductCategoryRepository.class);
        Alibaba1688Product relationMember = product("offer-member", 0);
        Alibaba1688Product legacyOnly = product("offer-legacy", 1);
        when(productRepository.findByTenantIdOrderBySyncedAtDesc(1L))
                .thenReturn(List.of(relationMember, legacyOnly));
        when(categoryRepository.findByTenantIdAndCategoryCode(1L, "growth_potential"))
                .thenReturn(List.of(category("row-member", "offer-member", "growth_potential")));

        Alibaba1688ProductService service = serviceWith(productRepository, categoryRepository);
        Map<String, Object> listed = service.listProducts("potential", "all", null);

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> items = (List<Map<String, Object>>) listed.get("items");
        assertEquals(List.of("offer-member"), items.stream().map(row -> row.get("offerId")).toList());
    }

    private Alibaba1688ProductService serviceWith(
            Alibaba1688ProductRepository productRepository,
            Alibaba1688ProductCategoryRepository categoryRepository
    ) {
        DataScopeService dataScopeService = mock(DataScopeService.class);
        when(dataScopeService.requireTenantId()).thenReturn(1L);
        return new Alibaba1688ProductService(
                dataScopeService,
                new AuthContext(),
                mock(AgentPresenceService.class),
                mock(Alibaba1688SessionService.class),
                productRepository,
                categoryRepository,
                mock(JdbcTemplate.class),
                new ObjectMapper(),
                new Alibaba1688StoreKeyResolver(mock(JdbcTemplate.class), new ObjectMapper())
        );
    }

    private Alibaba1688ProductCategory category(String id, String offerId, String categoryCode) {
        Alibaba1688ProductCategory row = new Alibaba1688ProductCategory();
        row.setId(id);
        row.setTenantId(1L);
        row.setStoreId("default");
        row.setOfferId(offerId);
        row.setCategoryCode(categoryCode);
        row.setCreatedAt("2026-08-18 18:00:00");
        return row;
    }

    private Alibaba1688Product product(String offerId, int legacyPotential) {
        Alibaba1688Product row = new Alibaba1688Product();
        row.setId("product-" + offerId);
        row.setTenantId(1L);
        row.setStoreId("default");
        row.setOfferId(offerId);
        row.setProductName(offerId);
        row.setTagPotential(legacyPotential);
        return row;
    }
    @Test
    void listPendingUsesCategoryRelationInsteadOfProductStatus() {
        Alibaba1688ProductRepository productRepository = mock(Alibaba1688ProductRepository.class);
        Alibaba1688ProductCategoryRepository categoryRepository = mock(Alibaba1688ProductCategoryRepository.class);
        Alibaba1688Product relationMember = product("offer-member", 0);
        relationMember.setStatus("on_sale");
        Alibaba1688Product legacyOnly = product("offer-legacy", 0);
        legacyOnly.setStatus("pending_list");
        when(productRepository.findByTenantIdOrderBySyncedAtDesc(1L))
                .thenReturn(List.of(relationMember, legacyOnly));
        when(categoryRepository.findByTenantIdAndCategoryCode(1L, "status_pending_list"))
                .thenReturn(List.of(category("row-pending", "offer-member", "status_pending_list")));

        Map<String, Object> listed = serviceWith(productRepository, categoryRepository)
                .listProducts("pending_list", "all", null);

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> items = (List<Map<String, Object>>) listed.get("items");
        assertEquals(List.of("offer-member"), items.stream().map(row -> row.get("offerId")).toList());
    }

    @Test
    void listProductsReturnsAllCategoryCounts() {
        Alibaba1688ProductRepository productRepository = mock(Alibaba1688ProductRepository.class);
        Alibaba1688ProductCategoryRepository categoryRepository = mock(Alibaba1688ProductCategoryRepository.class);
        when(productRepository.findByTenantIdOrderBySyncedAtDesc(1L)).thenReturn(List.of(product("offer-1", 0)));
        when(categoryRepository.findByTenantId(1L)).thenReturn(List.of(
                category("row-1", "offer-1", "growth_potential"),
                category("row-2", "offer-1", "status_on_sale")
        ));

        Map<String, Object> listed = serviceWith(productRepository, categoryRepository)
                .listProducts("all", "all", null);

        @SuppressWarnings("unchecked")
        Map<String, Integer> counts = (Map<String, Integer>) listed.get("categoryCounts");
        assertEquals(1, counts.get("growth_potential"));
        assertEquals(1, counts.get("status_on_sale"));
        assertEquals(0, counts.get("status_draft"));
    }

}
