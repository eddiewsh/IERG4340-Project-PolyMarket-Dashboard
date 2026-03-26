create extension if not exists vector;

create table if not exists public.rag_documents (
  id uuid primary key default gen_random_uuid(),
  source text not null,
  source_id text,
  title text,
  content text not null,
  url text,
  metadata jsonb not null default '{}'::jsonb,
  embedding vector(3072) not null,
  created_at timestamptz not null default now()
);

create index if not exists rag_documents_embedding_ivfflat
on public.rag_documents using ivfflat (embedding vector_cosine_ops) with (lists = 100);

create or replace function public.match_rag_documents(
  query_embedding vector(3072),
  match_count int,
  filter_source text default null
)
returns table (
  id uuid,
  source text,
  source_id text,
  title text,
  content text,
  url text,
  metadata jsonb,
  created_at timestamptz,
  similarity float
)
language sql stable
as $$
  select
    d.id,
    d.source,
    d.source_id,
    d.title,
    d.content,
    d.url,
    d.metadata,
    d.created_at,
    1 - (d.embedding <=> query_embedding) as similarity
  from public.rag_documents d
  where (filter_source is null or d.source = filter_source)
  order by d.embedding <=> query_embedding
  limit match_count;
$$;

