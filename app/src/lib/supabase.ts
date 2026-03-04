/**
 * Lightweight PostgREST client — replaces @supabase/supabase-js entirely.
 * Eliminates Realtime WebSocket + Auth modules that were causing
 * "Connection interrupted while trying to subscribe" errors.
 */

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

interface QueryResult<T = Record<string, unknown>> {
  data: T[] | null;
  error: { message: string } | null;
}

interface QueryBuilder {
  select(columns: string): QueryBuilder;
  eq(column: string, value: string | number): QueryBuilder;
  order(column: string, opts?: { ascending?: boolean }): QueryBuilder;
  limit(count: number): QueryBuilder;
  then<TResult>(
    onfulfilled?: (value: QueryResult) => TResult,
  ): Promise<TResult>;
  [Symbol.toStringTag]: string;
}

function buildQuery(table: string): QueryBuilder {
  const params = new URLSearchParams();
  let selectCols = "*";

  const builder: QueryBuilder = {
    select(columns: string) {
      selectCols = columns;
      return builder;
    },
    eq(column: string, value: string | number) {
      params.set(column, `eq.${value}`);
      return builder;
    },
    order(column: string, opts?: { ascending?: boolean }) {
      const dir = opts?.ascending === false ? "desc" : "asc";
      params.set("order", `${column}.${dir}`);
      return builder;
    },
    limit(count: number) {
      params.set("limit", String(count));
      return builder;
    },
    then(onfulfilled) {
      params.set("select", selectCols);
      const url = `${SUPABASE_URL}/rest/v1/${table}?${params.toString()}`;
      const promise = fetch(url, {
        headers: {
          apikey: SUPABASE_KEY,
          Authorization: `Bearer ${SUPABASE_KEY}`,
        },
      }).then(async (res) => {
        if (!res.ok) {
          const text = await res.text().catch(() => res.statusText);
          return { data: null, error: { message: text } } as QueryResult;
        }
        const data = await res.json();
        return { data, error: null } as QueryResult;
      });
      return onfulfilled ? promise.then(onfulfilled) : (promise as Promise<never>);
    },
    [Symbol.toStringTag]: "QueryBuilder",
  };

  return builder;
}

export const supabase = {
  from(table: string) {
    return buildQuery(table);
  },
};
