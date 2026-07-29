package com.crosshub.temu.service;

import java.util.Map;

public interface TemuSessionService {
    Map<String, Object> getSessionStatus();
    Map<String, Object> openLoginWindow();
    Map<String, Object> openFrontendLoginWindow(String url);
}

