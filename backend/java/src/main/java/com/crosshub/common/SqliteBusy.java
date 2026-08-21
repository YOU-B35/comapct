package com.crosshub.common;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.function.Supplier;

/**
 * SQLite 单写者限制下的兜底重试：
 * WAL 模式下并发写事务可能抛出 SQLITE_BUSY / SQLITE_BUSY_SNAPSHOT，
 * busy_timeout 对 SNAPSHOT 类错误无效，必须整体重试事务。
 */
public final class SqliteBusy {
    private static final Logger log = LoggerFactory.getLogger(SqliteBusy.class);

    private static final int MAX_ATTEMPTS = 4;

    private SqliteBusy() {
    }

    public static <T> T retry(Supplier<T> action) {
        int attempt = 0;
        while (true) {
            try {
                return action.get();
            } catch (RuntimeException ex) {
                if (isSqliteBusy(ex) && attempt < MAX_ATTEMPTS) {
                    attempt++;
                    long backoffMs = 500L * attempt * attempt;
                    log.warn("[SqliteBusy] database busy, retry {}/{} in {}ms: {}",
                            attempt, MAX_ATTEMPTS, backoffMs, rootMessage(ex));
                    try {
                        Thread.sleep(backoffMs);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        throw ex;
                    }
                    continue;
                }
                throw ex;
            }
        }
    }

    public static void run(Runnable action) {
        retry(() -> {
            action.run();
            return null;
        });
    }

    private static boolean isSqliteBusy(Throwable ex) {
        Throwable t = ex;
        while (t != null) {
            String msg = t.getMessage();
            if (msg != null && (msg.contains("SQLITE_BUSY") || msg.contains("database is locked"))) {
                return true;
            }
            t = t.getCause();
        }
        return false;
    }

    private static String rootMessage(Throwable ex) {
        Throwable t = ex;
        while (t.getCause() != null) {
            t = t.getCause();
        }
        String msg = t.getMessage();
        return msg == null ? t.getClass().getSimpleName() : msg;
    }
}
