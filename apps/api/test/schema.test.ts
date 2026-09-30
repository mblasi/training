import { describe, test, expect } from 'vitest';
import { getTableConfig, PgDialect } from 'drizzle-orm/pg-core';
import type { SQL } from 'drizzle-orm';
import { users, profiles, llmProviders, llmRoutes, llmCalls, agentPrompts } from '../src/db/schema/index.js';

describe('users table', () => {
  test('test_users_table_has_correct_columns', () => {
    const config = getTableConfig(users);
    const columns = config.columns;

    const id = columns.find((c) => c.name === 'id');
    const firebaseUid = columns.find((c) => c.name === 'firebase_uid');
    const email = columns.find((c) => c.name === 'email');
    const role = columns.find((c) => c.name === 'role');
    const locale = columns.find((c) => c.name === 'locale');
    const createdAt = columns.find((c) => c.name === 'created_at');

    expect(id).toBeDefined();
    expect(id!.columnType).toBe('PgUUID');

    expect(firebaseUid).toBeDefined();
    expect(firebaseUid!.columnType).toBe('PgText');
    expect(firebaseUid!.notNull).toBe(true);

    expect(email).toBeDefined();
    expect(email!.columnType).toBe('PgText');
    expect(email!.notNull).toBe(true);

    expect(role).toBeDefined();
    expect(role!.columnType).toBe('PgText');
    expect(role!.notNull).toBe(true);

    expect(locale).toBeDefined();
    expect(locale!.columnType).toBe('PgText');
    expect(locale!.notNull).toBe(true);

    expect(createdAt).toBeDefined();
    expect(createdAt!.columnType).toBe('PgTimestamp');
    expect(createdAt!.notNull).toBe(true);
  });

  test('test_users_id_has_uuidv7_default', () => {
    const config = getTableConfig(users);
    const columns = config.columns;
    const id = columns.find((c) => c.name === 'id');

    expect(id).toBeDefined();
    expect(id!.default).toBeDefined();

    const dialect = new PgDialect();
    const defaultSql = dialect.sqlToQuery(id!.default as SQL).sql;
    expect(defaultSql).toContain('uuidv7()');
  });

  test('test_users_role_has_check_constraint', () => {
    const config = getTableConfig(users);
    const checks = config.checks;

    expect(checks.length).toBeGreaterThan(0);

    const roleCheck = checks.find((check) => {
      const dialect = new PgDialect();
      const checkSql = dialect.sqlToQuery(check.value).sql;
      return checkSql.includes('user') && checkSql.includes('admin');
    });

    expect(roleCheck).toBeDefined();
  });
});

describe('profiles table', () => {
  test('test_profiles_table_has_correct_columns', () => {
    const config = getTableConfig(profiles);
    const columns = config.columns;

    const userId = columns.find((c) => c.name === 'user_id');
    const birthdate = columns.find((c) => c.name === 'birthdate');
    const heightCm = columns.find((c) => c.name === 'height_cm');
    const activityLevel = columns.find((c) => c.name === 'activity_level');
    const experienceLevel = columns.find((c) => c.name === 'experience_level');
    const injuries = columns.find((c) => c.name === 'injuries');
    const updatedAt = columns.find((c) => c.name === 'updated_at');

    expect(userId).toBeDefined();
    expect(userId!.columnType).toBe('PgUUID');
    expect(userId!.notNull).toBe(true);

    expect(birthdate).toBeDefined();
    expect(birthdate!.columnType).toBe('PgDateString');

    expect(heightCm).toBeDefined();
    expect(heightCm!.columnType).toBe('PgInteger');

    expect(activityLevel).toBeDefined();
    expect(activityLevel!.columnType).toBe('PgText');

    expect(experienceLevel).toBeDefined();
    expect(experienceLevel!.columnType).toBe('PgText');

    expect(injuries).toBeDefined();
    expect(injuries!.columnType).toBe('PgJsonb');

    expect(updatedAt).toBeDefined();
    expect(updatedAt!.columnType).toBe('PgTimestamp');
    expect(updatedAt!.notNull).toBe(true);
  });

  test('test_profiles_user_id_is_fk_to_users', () => {
    const config = getTableConfig(profiles);
    const foreignKeys = config.foreignKeys;

    expect(foreignKeys.length).toBeGreaterThan(0);

    const userIdFk = foreignKeys.find((fk) => {
      const reference = fk.reference();
      const foreignTableName = getTableConfig(reference.foreignTable).name;
      const localColumns = reference.columns.map((c) => c.name);
      return foreignTableName === 'users' && localColumns.includes('user_id');
    });

    expect(userIdFk).toBeDefined();
  });
});

describe('llm_providers table', () => {
  test('test_llm_providers_table_has_correct_columns', () => {
    const config = getTableConfig(llmProviders);
    const columns = config.columns;

    const id = columns.find((c) => c.name === 'id');
    const name = columns.find((c) => c.name === 'name');
    const baseUrl = columns.find((c) => c.name === 'base_url');
    const secretRef = columns.find((c) => c.name === 'secret_ref');
    const enabled = columns.find((c) => c.name === 'enabled');

    expect(id).toBeDefined();
    expect(id!.columnType).toBe('PgUUID');

    expect(name).toBeDefined();
    expect(name!.columnType).toBe('PgText');
    expect(name!.notNull).toBe(true);

    expect(baseUrl).toBeDefined();
    expect(baseUrl!.columnType).toBe('PgText');
    expect(baseUrl!.notNull).toBe(true);

    expect(secretRef).toBeDefined();
    expect(secretRef!.columnType).toBe('PgText');
    expect(secretRef!.notNull).toBe(true);

    expect(enabled).toBeDefined();
    expect(enabled!.columnType).toBe('PgBoolean');
    expect(enabled!.notNull).toBe(true);
  });

  test('test_llm_providers_name_has_check_constraint', () => {
    const config = getTableConfig(llmProviders);
    const checks = config.checks;

    expect(checks.length).toBeGreaterThan(0);

    const nameCheck = checks.find((check) => {
      const dialect = new PgDialect();
      const checkSql = dialect.sqlToQuery(check.value).sql;
      return checkSql.includes('nous') && checkSql.includes('gemini');
    });

    expect(nameCheck).toBeDefined();
  });
});

describe('llm_routes table', () => {
  test('test_llm_routes_pk_is_agent', () => {
    const config = getTableConfig(llmRoutes);
    const columns = config.columns;

    const agent = columns.find((c) => c.name === 'agent');
    expect(agent).toBeDefined();
    expect(agent!.primary).toBe(true);

    // Verificar que es la única columna con primary
    const primaryColumns = columns.filter((c) => c.primary === true);
    expect(primaryColumns.length).toBe(1);
  });

  test('test_llm_routes_has_fk_to_providers', () => {
    const config = getTableConfig(llmRoutes);
    const foreignKeys = config.foreignKeys;

    expect(foreignKeys.length).toBeGreaterThan(0);

    const providerIdFk = foreignKeys.find((fk) => {
      const reference = fk.reference();
      const foreignTableName = getTableConfig(reference.foreignTable).name;
      const localColumns = reference.columns.map((c) => c.name);
      return foreignTableName === 'llm_providers' && localColumns.includes('provider_id');
    });

    expect(providerIdFk).toBeDefined();
  });
});

describe('llm_calls table', () => {
  test('test_llm_calls_has_required_columns', () => {
    const config = getTableConfig(llmCalls);
    const columns = config.columns;

    const tokensIn = columns.find((c) => c.name === 'tokens_in');
    const tokensOut = columns.find((c) => c.name === 'tokens_out');
    const costUsd = columns.find((c) => c.name === 'cost_usd');
    const latencyMs = columns.find((c) => c.name === 'latency_ms');
    const contextBreakdown = columns.find((c) => c.name === 'context_breakdown');
    const provider = columns.find((c) => c.name === 'provider');

    expect(tokensIn).toBeDefined();
    expect(tokensIn!.columnType).toBe('PgInteger');
    expect(tokensIn!.notNull).toBe(true);

    expect(tokensOut).toBeDefined();
    expect(tokensOut!.columnType).toBe('PgInteger');
    expect(tokensOut!.notNull).toBe(true);

    expect(costUsd).toBeDefined();
    expect(costUsd!.columnType).toBe('PgNumeric');
    expect(costUsd!.notNull).toBe(true);

    expect(latencyMs).toBeDefined();
    expect(latencyMs!.columnType).toBe('PgInteger');
    expect(latencyMs!.notNull).toBe(true);

    expect(contextBreakdown).toBeDefined();
    expect(contextBreakdown!.columnType).toBe('PgJsonb');
    expect(contextBreakdown!.notNull).toBe(true);

    expect(provider).toBeDefined();
    expect(provider!.columnType).toBe('PgText');
    expect(provider!.notNull).toBe(true);
  });

  test('test_llm_calls_id_has_uuidv7_default', () => {
    const config = getTableConfig(llmCalls);
    const columns = config.columns;
    const id = columns.find((c) => c.name === 'id');

    expect(id).toBeDefined();
    expect(id!.default).toBeDefined();

    const dialect = new PgDialect();
    const defaultSql = dialect.sqlToQuery(id!.default as SQL).sql;
    expect(defaultSql).toContain('uuidv7()');
  });
});

describe('agent_prompts table', () => {
  test('test_agent_prompts_table_has_correct_columns', () => {
    const config = getTableConfig(agentPrompts);
    const columns = config.columns;

    const id = columns.find((c) => c.name === 'id');
    const agent = columns.find((c) => c.name === 'agent');
    const version = columns.find((c) => c.name === 'version');
    const content = columns.find((c) => c.name === 'content');
    const status = columns.find((c) => c.name === 'status');
    const author = columns.find((c) => c.name === 'author');
    const notes = columns.find((c) => c.name === 'notes');
    const createdAt = columns.find((c) => c.name === 'created_at');

    expect(id).toBeDefined();
    expect(id!.columnType).toBe('PgUUID');

    expect(agent).toBeDefined();
    expect(agent!.columnType).toBe('PgText');
    expect(agent!.notNull).toBe(true);

    expect(version).toBeDefined();
    expect(version!.columnType).toBe('PgInteger');
    expect(version!.notNull).toBe(true);

    expect(content).toBeDefined();
    expect(content!.columnType).toBe('PgText');
    expect(content!.notNull).toBe(true);

    expect(status).toBeDefined();
    expect(status!.columnType).toBe('PgText');
    expect(status!.notNull).toBe(true);

    expect(author).toBeDefined();
    expect(author!.columnType).toBe('PgUUID');
    expect(author!.notNull).toBe(true);

    expect(notes).toBeDefined();
    expect(notes!.columnType).toBe('PgText');
    expect(notes!.notNull).toBe(false);

    expect(createdAt).toBeDefined();
    expect(createdAt!.columnType).toBe('PgTimestamp');
    expect(createdAt!.notNull).toBe(true);
  });

  test('test_agent_prompts_status_has_check_constraint', () => {
    const config = getTableConfig(agentPrompts);
    const checks = config.checks;

    expect(checks.length).toBeGreaterThan(0);

    const statusCheck = checks.find((check) => {
      const dialect = new PgDialect();
      const checkSql = dialect.sqlToQuery(check.value).sql;
      return checkSql.includes('draft') && checkSql.includes('published') && checkSql.includes('archived');
    });

    expect(statusCheck).toBeDefined();
  });

  test('test_agent_prompts_id_has_uuidv7_default', () => {
    const config = getTableConfig(agentPrompts);
    const columns = config.columns;
    const id = columns.find((c) => c.name === 'id');

    expect(id).toBeDefined();
    expect(id!.default).toBeDefined();

    const dialect = new PgDialect();
    const defaultSql = dialect.sqlToQuery(id!.default as SQL).sql;
    expect(defaultSql).toContain('uuidv7()');
  });
});
