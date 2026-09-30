import { describe, test, expect } from 'vitest';
import { getTableConfig } from 'drizzle-orm/pg-core/utils';
import { PgDialect } from 'drizzle-orm/pg-core/dialect';
import { users, profiles } from '../src/db/schema/index.js';

const dialect = new PgDialect();

describe('schema: users table', () => {
  test('test_users_table_has_correct_columns', () => {
    const config = getTableConfig(users);
    
    const id = config.columns.find((c) => c.name === 'id');
    const firebaseUid = config.columns.find((c) => c.name === 'firebase_uid');
    const email = config.columns.find((c) => c.name === 'email');
    const role = config.columns.find((c) => c.name === 'role');
    const locale = config.columns.find((c) => c.name === 'locale');
    const createdAt = config.columns.find((c) => c.name === 'created_at');
    
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
    const id = config.columns.find((c) => c.name === 'id');
    
    expect(id).toBeDefined();
    
    const hasDefault = id?.default !== undefined || id?.defaultFn !== undefined;
    expect(hasDefault).toBe(true);
    
    if (id?.default) {
      const sql = dialect.sqlToQuery(id.default).sql;
      expect(sql).toContain('uuidv7()');
    } else if (id?.defaultFn) {
      const defaultValue = id.defaultFn();
      const sql = dialect.sqlToQuery(defaultValue).sql;
      expect(sql).toContain('uuidv7()');
    }
  });

  test('test_users_role_has_check_constraint', () => {
    const config = getTableConfig(users);
    
    expect(config.checks.length).toBeGreaterThan(0);
    
    const roleCheck = config.checks.find((check) => {
      const sql = dialect.sqlToQuery(check.value).sql;
      return sql.includes('user') && sql.includes('admin');
    });
    
    expect(roleCheck).toBeDefined();
  });
});

describe('schema: profiles table', () => {
  test('test_profiles_table_has_correct_columns', () => {
    const config = getTableConfig(profiles);
    
    const userId = config.columns.find((c) => c.name === 'user_id');
    const birthdate = config.columns.find((c) => c.name === 'birthdate');
    const heightCm = config.columns.find((c) => c.name === 'height_cm');
    const activityLevel = config.columns.find((c) => c.name === 'activity_level');
    const experienceLevel = config.columns.find((c) => c.name === 'experience_level');
    const injuries = config.columns.find((c) => c.name === 'injuries');
    const updatedAt = config.columns.find((c) => c.name === 'updated_at');
    
    expect(userId).toBeDefined();
    expect(userId?.columnType).toBe('PgUUID');
    
    expect(birthdate).toBeDefined();
    expect(birthdate?.columnType).toBe('PgDate');
    
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
    
    expect(config.foreignKeys.length).toBeGreaterThan(0);
    
    const userIdFk = config.foreignKeys.find((fk) => {
      const ref = fk.reference();
      const foreignTableName = getTableConfig(ref.foreignTable).name;
      const column = ref.columns[0];
      return column.name === 'user_id' && foreignTableName === 'users';
    });
    
    expect(userIdFk).toBeDefined();
  });
});
