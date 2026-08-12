package com.crosshub.commander.controller;

import com.crosshub.commander.service.CommanderProxyService;
import com.crosshub.security.AuthContext;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;

@RestController
public class CommanderProxyController {
    private final CommanderProxyService proxyService;
    private final AuthContext authContext;

    public CommanderProxyController(CommanderProxyService proxyService, AuthContext authContext) {
        this.proxyService = proxyService;
        this.authContext = authContext;
    }

    @RequestMapping(
            value = "/api/commander/v1/**",
            method = {
                    RequestMethod.GET,
                    RequestMethod.POST,
                    RequestMethod.PUT,
                    RequestMethod.PATCH,
                    RequestMethod.DELETE
            }
    )
    public ResponseEntity<byte[]> proxy(HttpServletRequest request) throws IOException {
        requirePortalUser();
        String pathAndQuery = CommanderProxyService.toCommanderPath(
                request.getRequestURI(),
                request.getQueryString()
        );
        byte[] body = request.getInputStream().readAllBytes();
        return proxyService.forward(request.getMethod(), pathAndQuery, body, request.getContentType());
    }

    private void requirePortalUser() {
        if (authContext.get() == null || authContext.userId() == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "未登录");
        }
        String portal = String.valueOf(authContext.portalRole() == null ? "" : authContext.portalRole());
        if (!"boss".equalsIgnoreCase(portal) && !"employee".equalsIgnoreCase(portal)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "仅 Boss/员工端可使用自动上货");
        }
    }
}
