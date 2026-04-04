-- Configurable prompt sections for intelligence agents
-- Allows tuning agent prompts via DB without code deploys

create table if not exists wp_prompt_templates (
    id uuid primary key default gen_random_uuid(),
    agent_name text not null,           -- quant, snoop, sage, brief
    section text not null,              -- role, input_format, output_schema, constraints, reasoning_instructions, examples
    content text not null,
    is_active boolean default true,
    version int default 1,
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    unique(agent_name, section, version)
);

create index idx_prompt_templates_agent on wp_prompt_templates(agent_name, is_active);
