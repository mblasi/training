import { describe, test, expect } from 'vitest';
import { getTableConfig, PgDialect } from 'drizzle-orm/pg-core';
import { users, profiles } from '../src/db/schema/index.js';

describe('Schema: users table', () => {
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
    expect(id?.columnType).toBe('PgUUID');

    expect(firebaseUid).toBeDefined();
    expect(firebaseUid?.columnType).toBe('PgText');

    expect(email).toBeDefined();
    expect(email?.columnType).toBe('PgText');

    expect(role).toBeDefined();
    expect(role?.columnType).toBe('PgText');

    expect(locale).toBeDefined();
    expect(locale?.columnType).toBe('PgText');

    expect(createdAt).toBeDefined();
    expect(createdAt?.columnType).toBe('PgTimestamp');
  });

  test('test_users_id_has_uuidv7_default', () => {
    const config = getTableConfig(users);
    const columns = config.columns;
    const id = columns.find((c) => c.name === 'id');

    expect(id).toBeDefined();
    expect(id?.default).toBeDefined();

    const dialect = new PgDialect();
    const defaultSql = dialect.sqlToQuery(id!.default!).sql;

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

describe('Schema: profiles table', () => {
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
    expect(userId?.columnType).toBe('PgUUID');

    expect(birthdate).toBeDefined();
    expect(birthdate?.columnType).toBe('PgText');

    expect(heightCm).toBeDefined();
    expect(heightCm?.columnType).toBe('PgInteger');

    expect(activityLevel).toBeDefined();
    expect(activityLevel?.columnType).toBe('PgText');

    expect(experienceLevel).toBeDefined();
    expect(experienceLevel?.columnType).toBe('PgText');

    expect(injuries).toBeDefined();
    expect(injuries?.columnType).toBe('PgJsonb');

    expect(updatedAt).toBeDefined();
    expect(updatedAt?.columnType).toBe('PgTimestamp');
  });

  test('test_profiles_user_id_is_fk_to_users', () => {
    const config = getTableConfig(profiles);
    const foreignKeys = config.foreignKeys;

    expect(foreignKeys.length).toBeGreaterThan(0);

    const userIdFk = foreignKeys.find((fk) => {
      const ref = fk.reference();
      const foreignTableName = getTableConfig(ref.foreignTable).name;
      const hasUserIdColumn = ref.columns.some((col) => col.name === 'user_id');
      return foreignTableName === 'users' && hasUserIdColumn;
    });

    expect(userIdFk).toBeDefined();
  });
});
