package com.crosshub.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "crosshub.agent")
public class AgentProperties {
    private Concurrency concurrency = new Concurrency();

    public Concurrency getConcurrency() {
        return concurrency;
    }

    public void setConcurrency(Concurrency concurrency) {
        this.concurrency = concurrency == null ? new Concurrency() : concurrency;
    }

    public static class Concurrency {
        /** Temu 卖家浏览器并行上限（按 session_key 互斥） */
        private int maxTemu = 3;
        /** 速卖通浏览器并行上限 */
        private int maxAliExpress = 2;
        /** Amazon（紫鸟）并行上限 */
        private int maxAmazon = 1;
        /** 全局浏览器槽位 */
        private int maxGlobal = 5;
        /** 单次 poll 最多认领任务数 */
        private int maxClaimBatch = 5;
        /** 单条 temu_crawl 多会话时按多少会话占槽 */
        private int temuParallelSessions = 3;

        public int getMaxTemu() { return maxTemu; }
        public void setMaxTemu(int maxTemu) { this.maxTemu = Math.max(1, maxTemu); }
        public int getMaxAliExpress() { return maxAliExpress; }
        public void setMaxAliExpress(int maxAliExpress) { this.maxAliExpress = Math.max(1, maxAliExpress); }
        public int getMaxAmazon() { return maxAmazon; }
        public void setMaxAmazon(int maxAmazon) { this.maxAmazon = Math.max(1, maxAmazon); }
        public int getMaxGlobal() { return maxGlobal; }
        public void setMaxGlobal(int maxGlobal) { this.maxGlobal = Math.max(1, maxGlobal); }
        public int getMaxClaimBatch() { return maxClaimBatch; }
        public void setMaxClaimBatch(int maxClaimBatch) { this.maxClaimBatch = Math.max(1, maxClaimBatch); }
        public int getTemuParallelSessions() { return temuParallelSessions; }
        public void setTemuParallelSessions(int temuParallelSessions) {
            this.temuParallelSessions = Math.max(1, temuParallelSessions);
        }
    }
}
