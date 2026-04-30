-- ============================================================================
-- CONFIG
-- ============================================================================

CREATE TABLE bot_config (
    id SERIAL PRIMARY KEY,
    enabled BOOLEAN DEFAULT FALSE,
    mode TEXT CHECK (mode IN ('logger', 'paper', 'live')) DEFAULT 'logger',
    active_strategies JSONB DEFAULT '[]'::jsonb,
    max_position_size_usdc NUMERIC DEFAULT 10,
    hourly_profit_target_usdc NUMERIC DEFAULT 2,
    hourly_stop_loss_usdc NUMERIC DEFAULT -3,
    daily_profit_target_usdc NUMERIC DEFAULT 20,
    daily_stop_loss_usdc NUMERIC DEFAULT -15,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO bot_config (enabled, mode) VALUES (FALSE, 'logger');

-- ============================================================================
-- MARKETS
-- ============================================================================

CREATE TABLE markets (
    market_id TEXT PRIMARY KEY,
    condition_id TEXT,
    question TEXT NOT NULL,
    asset TEXT,
    market_type TEXT,
    duration_seconds INTEGER,
    open_time TIMESTAMPTZ NOT NULL,
    close_time TIMESTAMPTZ NOT NULL,

    chainlink_price_open NUMERIC,
    chainlink_price_open_ts TIMESTAMPTZ,
    chainlink_price_close NUMERIC,
    chainlink_price_close_ts TIMESTAMPTZ,

    resolution TEXT,
    resolved_at TIMESTAMPTZ,

    asset_id_up TEXT,
    asset_id_down TEXT,

    raw_payload JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_markets_open_time ON markets(open_time DESC);
CREATE INDEX idx_markets_type ON markets(market_type);
CREATE INDEX idx_markets_resolution ON markets(resolution) WHERE resolution IS NOT NULL;

-- ============================================================================
-- PRICE FEEDS
-- ============================================================================

CREATE TABLE chainlink_btc_feed (
    ts TIMESTAMPTZ NOT NULL,
    received_ts TIMESTAMPTZ NOT NULL,
    price NUMERIC NOT NULL,
    source TEXT DEFAULT 'polymarket_rtds',
    PRIMARY KEY (ts, source)
);

CREATE INDEX idx_chainlink_ts ON chainlink_btc_feed(ts DESC);

CREATE TABLE binance_btc_feed (
    ts TIMESTAMPTZ NOT NULL,
    received_ts TIMESTAMPTZ NOT NULL,
    price NUMERIC NOT NULL,
    volume_1s NUMERIC,
    buy_volume_1s NUMERIC,
    sell_volume_1s NUMERIC,
    trade_count_1s INTEGER,
    source TEXT NOT NULL,
    PRIMARY KEY (ts, source)
);

CREATE INDEX idx_binance_ts ON binance_btc_feed(ts DESC);

CREATE OR REPLACE VIEW binance_btc_feed_consolidated AS
SELECT DISTINCT ON (ts)
    ts, price, volume_1s, buy_volume_1s, sell_volume_1s, source
FROM binance_btc_feed
ORDER BY ts,
    CASE source
        WHEN 'binance_direct' THEN 1
        WHEN 'polymarket_rtds' THEN 2
    END;

-- ============================================================================
-- ORDER BOOK
-- ============================================================================

CREATE TABLE orderbook_snapshots (
    id BIGSERIAL PRIMARY KEY,
    market_id TEXT REFERENCES markets(market_id),
    side TEXT CHECK (side IN ('UP', 'DOWN')),
    snapshot_time TIMESTAMPTZ NOT NULL,
    seconds_till_end INTEGER,
    best_bid NUMERIC,
    best_ask NUMERIC,
    bid_depth_5 JSONB,
    ask_depth_5 JSONB,
    mid_price NUMERIC GENERATED ALWAYS AS ((best_bid + best_ask) / 2) STORED,
    spread NUMERIC GENERATED ALWAYS AS (best_ask - best_bid) STORED,
    microprice NUMERIC,
    imbalance NUMERIC
);

CREATE INDEX idx_ob_market_time ON orderbook_snapshots(market_id, snapshot_time);
CREATE INDEX idx_ob_seconds_till_end ON orderbook_snapshots(market_id, seconds_till_end);

CREATE TABLE polymarket_trades (
    id BIGSERIAL PRIMARY KEY,
    market_id TEXT REFERENCES markets(market_id),
    side TEXT,
    price NUMERIC,
    size NUMERIC,
    trade_time TIMESTAMPTZ NOT NULL,
    raw_payload JSONB
);

CREATE INDEX idx_pmtrades_market_time ON polymarket_trades(market_id, trade_time);

-- ============================================================================
-- FEATURES
-- ============================================================================

CREATE TABLE market_features (
    id BIGSERIAL PRIMARY KEY,
    market_id TEXT REFERENCES markets(market_id),
    decision_moment TEXT NOT NULL,
    decision_time TIMESTAMPTZ NOT NULL,
    seconds_till_end INTEGER,

    path_return NUMERIC,
    path_high NUMERIC,
    path_low NUMERIC,
    path_volatility NUMERIC,

    btc_price_now NUMERIC,
    btc_return_30s NUMERIC,
    btc_return_60s NUMERIC,
    btc_return_120s NUMERIC,
    btc_return_300s NUMERIC,
    btc_volatility_60s NUMERIC,
    btc_volatility_300s NUMERIC,
    btc_volume_60s NUMERIC,
    btc_buy_sell_imbalance_60s NUMERIC,

    cl_bn_diff NUMERIC,
    cl_bn_diff_30s_avg NUMERIC,
    cl_lag_estimate_ms INTEGER,

    pm_up_best_bid NUMERIC,
    pm_up_best_ask NUMERIC,
    pm_up_imbalance NUMERIC,
    pm_down_best_bid NUMERIC,
    pm_down_best_ask NUMERIC,
    pm_down_imbalance NUMERIC,
    pm_implied_p_up NUMERIC,

    UNIQUE (market_id, decision_moment)
);

CREATE INDEX idx_features_market ON market_features(market_id);
CREATE INDEX idx_features_moment ON market_features(decision_moment);

-- ============================================================================
-- DECISIONES Y EJECUCIONES
-- ============================================================================

CREATE TABLE bot_decisions (
    id BIGSERIAL PRIMARY KEY,
    market_id TEXT REFERENCES markets(market_id),
    decision_time TIMESTAMPTZ NOT NULL,
    decision_moment TEXT,
    strategy_name TEXT,
    mode TEXT CHECK (mode IN ('paper', 'live')),
    action TEXT CHECK (action IN ('BUY_UP', 'BUY_DOWN', 'SKIP')),
    confidence NUMERIC,
    rationale JSONB,
    intended_size_usdc NUMERIC,
    intended_price NUMERIC,
    risk_check_passed BOOLEAN,
    risk_check_reason TEXT
);

CREATE TABLE bot_executions (
    id BIGSERIAL PRIMARY KEY,
    decision_id BIGINT REFERENCES bot_decisions(id),
    market_id TEXT REFERENCES markets(market_id),
    strategy_name TEXT,
    mode TEXT,
    side TEXT,
    fill_price NUMERIC,
    fill_size NUMERIC,
    fill_time TIMESTAMPTZ,
    cost_usdc NUMERIC,
    fees_usdc NUMERIC,
    pm_order_id TEXT,
    status TEXT,
    exit_price NUMERIC,
    pnl_usdc NUMERIC,
    closed_at TIMESTAMPTZ
);

CREATE INDEX idx_exec_market ON bot_executions(market_id);
CREATE INDEX idx_exec_strategy ON bot_executions(strategy_name);
CREATE INDEX idx_exec_mode_time ON bot_executions(mode, fill_time DESC);

-- ============================================================================
-- VIEWS DE PnL
-- ============================================================================

CREATE MATERIALIZED VIEW pnl_hourly AS
SELECT
    date_trunc('hour', fill_time) AS hour,
    mode,
    strategy_name,
    COUNT(*) AS trades,
    SUM(pnl_usdc) AS total_pnl,
    AVG(pnl_usdc) AS avg_pnl_per_trade,
    SUM(CASE WHEN pnl_usdc > 0 THEN 1 ELSE 0 END)::float / COUNT(*) AS hit_rate
FROM bot_executions
WHERE status = 'filled'
GROUP BY date_trunc('hour', fill_time), mode, strategy_name;

CREATE MATERIALIZED VIEW pnl_daily AS
SELECT
    date_trunc('day', fill_time) AS day,
    mode,
    strategy_name,
    COUNT(*) AS trades,
    SUM(pnl_usdc) AS total_pnl,
    SUM(CASE WHEN pnl_usdc > 0 THEN 1 ELSE 0 END)::float / COUNT(*) AS hit_rate,
    MAX(pnl_usdc) AS best_trade,
    MIN(pnl_usdc) AS worst_trade
FROM bot_executions
WHERE status = 'filled'
GROUP BY date_trunc('day', fill_time), mode, strategy_name;

-- ============================================================================
-- LOGS
-- ============================================================================

CREATE TABLE bot_logs (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ DEFAULT NOW(),
    service TEXT,
    level TEXT,
    message TEXT,
    context JSONB
);

CREATE INDEX idx_logs_ts ON bot_logs(ts DESC);
CREATE INDEX idx_logs_service_level ON bot_logs(service, level);
