package com.crosshub.amazon.service.impl;

import com.crosshub.amazon.entity.AmazonOperationalItem;
import com.crosshub.amazon.repository.AmazonOperationalItemRepository;
import com.crosshub.amazon.repository.AmazonWriteJobRepository;
import com.crosshub.platform.entity.PlatformAccount;
import com.crosshub.platform.repository.PlatformAccountRepository;
import com.crosshub.security.AuthContext;
import com.crosshub.tenant.service.DataScopeService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class AmazonWriteServiceImplShipGuardTest {

    @Test
    void shipOutboundRejectsFbaOrder() {
        DataScopeService dataScopeService = mock(DataScopeService.class);
        AmazonOperationalItemRepository itemRepository = mock(AmazonOperationalItemRepository.class);
        PlatformAccountRepository platformAccountRepository = mock(PlatformAccountRepository.class);

        AmazonOperationalItem item = new AmazonOperationalItem();
        item.setId("item-fba");
        item.setTenantId(5L);
        item.setItemType("outbound_order");
        item.setPlatformAccountId("account-1");
        item.setPayloadJson("{\"order_no\":\"111-1111111-1111111\",\"fulfillment_type\":\"fba\"}");

        when(dataScopeService.requireTenantId()).thenReturn(5L);
        when(itemRepository.findById("item-fba")).thenReturn(Optional.of(item));
        PlatformAccount account = new PlatformAccount();
        account.setId("account-1");
        account.setTenantId(5L);
        when(platformAccountRepository.findByIdAndTenantId("account-1", 5L)).thenReturn(Optional.of(account));

        AmazonWriteServiceImpl service = new AmazonWriteServiceImpl(
                dataScopeService,
                new AuthContext(),
                itemRepository,
                mock(AmazonWriteJobRepository.class),
                platformAccountRepository,
                mock(JdbcTemplate.class),
                new ObjectMapper()
        );

        ResponseStatusException ex = assertThrows(
                ResponseStatusException.class,
                () -> service.shipOutbound("item-fba", "E2E-TRACK-001")
        );
        assertEquals(HttpStatus.BAD_REQUEST, ex.getStatusCode());
        assertEquals("FBA 订单由亚马逊履约，无需确认发货", ex.getReason());
    }
}
