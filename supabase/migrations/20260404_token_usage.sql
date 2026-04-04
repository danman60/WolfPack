-- Token usage telemetry — track LLM costs per agent, model, and symbol
create table if not exists wp_token_usage (
    id uuid primary key default gen_random_uuid(),
    agent_name text not null,
    model text,
    provider text,
    prompt_tokens int,
    completion_tokens int,
    total_tokens int,
    estimated_cost_usd numeric(10, 6),
    symbol text,
    created_at timestamptz default now()
);

create index idx_token_usage_agent on wp_token_usage(agent_name, created_at);
create index idx_token_usage_daily on wp_token_usage(created_at);
