package com.crosshub.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "crosshub.crawler")
public class CrawlerProperties {
    private String pythonExecutable = "py";
    private String scriptDir = "../backend/python";
    private int timeoutSeconds = 300;
    private boolean allowSeed = false;
    private boolean useAgent = true;
    private DailySync dailySync = new DailySync();

    public String getPythonExecutable() { return pythonExecutable; }
    public void setPythonExecutable(String pythonExecutable) { this.pythonExecutable = pythonExecutable; }
    public String getScriptDir() { return scriptDir; }
    public void setScriptDir(String scriptDir) { this.scriptDir = scriptDir; }
    public int getTimeoutSeconds() { return timeoutSeconds; }
    public void setTimeoutSeconds(int timeoutSeconds) { this.timeoutSeconds = timeoutSeconds; }
    public boolean isAllowSeed() { return allowSeed; }
    public void setAllowSeed(boolean allowSeed) { this.allowSeed = allowSeed; }
    public boolean isUseAgent() { return useAgent; }
    public void setUseAgent(boolean useAgent) { this.useAgent = useAgent; }
    public DailySync getDailySync() { return dailySync; }
    public void setDailySync(DailySync dailySync) { this.dailySync = dailySync == null ? new DailySync() : dailySync; }

    public static class DailySync {
        /** 全平台日批：Temu + 速卖通 + Amazon，默认每天 09:30 */
        private boolean enabled = true;
        /** Spring cron：秒 分 时 日 月 周 */
        private String cron = "0 30 9 * * *";
        private String zone = "Asia/Shanghai";

        public boolean isEnabled() { return enabled; }
        public void setEnabled(boolean enabled) { this.enabled = enabled; }
        public String getCron() { return cron; }
        public void setCron(String cron) { this.cron = cron; }
        public String getZone() { return zone; }
        public void setZone(String zone) { this.zone = zone; }
    }
}
