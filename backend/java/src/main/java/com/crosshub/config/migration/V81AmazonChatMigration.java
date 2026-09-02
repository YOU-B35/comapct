package com.crosshub.config.migration;

import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@Order(81)
public class V81AmazonChatMigration {
    private final JdbcTemplate jdbc;

    public V81AmazonChatMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS amazon_chat_session (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  user_id INTEGER,
                  store_id TEXT NOT NULL,
                  platform TEXT NOT NULL DEFAULT 'amazon',
                  status TEXT NOT NULL DEFAULT 'pending',
                  created_at TEXT NOT NULL DEFAULT '',
                  updated_at TEXT NOT NULL DEFAULT ''
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS amazon_chat_message (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  session_id TEXT NOT NULL,
                  role TEXT NOT NULL,
                  content TEXT NOT NULL DEFAULT '',
                  tool_calls TEXT NOT NULL DEFAULT '{}',
                  created_at TEXT NOT NULL DEFAULT ''
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS amazon_chat_tool_log (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  session_id TEXT NOT NULL,
                  tool_name TEXT NOT NULL DEFAULT '',
                  args_json TEXT NOT NULL DEFAULT '{}',
                  result_summary TEXT NOT NULL DEFAULT '',
                  ok INTEGER NOT NULL DEFAULT 0,
                  duration_ms INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL DEFAULT ''
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS amazon_chat_memory (
                  id TEXT PRIMARY KEY,
                  tenant_id INTEGER NOT NULL,
                  store_id TEXT NOT NULL,
                  mem_key TEXT NOT NULL DEFAULT '',
                  mem_value TEXT NOT NULL DEFAULT '',
                  ttl_at TEXT NOT NULL DEFAULT '',
                  updated_at TEXT NOT NULL DEFAULT '',
                  UNIQUE (tenant_id, store_id, mem_key)
                )
                """);
        jdbc.execute("CREATE INDEX IF NOT EXISTS idx_amazon_chat_session_tenant_store ON amazon_chat_session (tenant_id, store_id, updated_at)");
        jdbc.execute("CREATE INDEX IF NOT EXISTS idx_amazon_chat_message_session ON amazon_chat_message (tenant_id, session_id, created_at)");
        jdbc.execute("CREATE INDEX IF NOT EXISTS idx_amazon_chat_tool_log_session ON amazon_chat_tool_log (tenant_id, session_id, created_at)");
        jdbc.execute("CREATE INDEX IF NOT EXISTS idx_amazon_chat_memory_store ON amazon_chat_memory (tenant_id, store_id, updated_at)");
    }
}
