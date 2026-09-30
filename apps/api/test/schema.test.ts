import { describe, test, expect } from 'vitest';
import { getTableConfig } from 'drizzle-orm/pg-core';
import { users, profiles } from '../src/db/schema/index.js';

describe('users table schema', () => {
  test('test_users_table_has_correct_columns', () => {
    const config = getTableConfig(users);
    const columns = config.columns;
    
    expect(columns).toHaveProperty('id');
    expect(columns).toHaveProperty('firebase_uid');
    expect(columns).toHaveProperty('email');
    expect(columns).toHaveProperty('role');
    expect(columns).toHaveProperty('locale');
    expect(columns).toHaveProperty('created_at');
    
    expect(columns.id.dataType).toBe('string');
    expect(columns.firebase_uid.dataType).toBe('string');
    expect(columns.email.dataType).toBe('string');
    expect(columns.role.dataType).toBe('string');
    expect(columns.locale.dataType).toBe('string');
    expect(columns.created_at.dataType).toBe('date');
  });

  test('test_users_id_has_uuidv7_default', () => {
    const config = getTableConfig(users);
    const idColumn = config.columns.id;
    
    // Verificar que tiene defaultFn o default que incluya uuidv7
    const hasDefault = idColumn.default !== undefined || idColumn.defaultFn !== undefined;
    expect(hasDefault).toBe(true);
    
    // Verificar que la definición incluye referencia a uuidv7()
    const defaultValue = idColumn.default || idColumn.defaultFn;
    if (defaultValue) {
      const defaultStr = defaultValue.toString();
      expect(defaultStr).toContain('uuidv7');
    }
  });

  test('test_users_role_has_check_constraint', () => {
    const config = getTableConfig(users);
    const checks = config.checks;
    
    expect(checks.length).toBeGreaterThan(0);
    
    // Buscar un check constraint que mencione 'user' y 'admin'
    const roleCheck = checks.find(check => {
      const checkStr = check.value.toString();
      return checkStr.includes('user') && checkStr.includes('admin');
    });
    
    expect(roleCheck).toBeDefined();
  });
});

describe('profiles table schema', () => {
  test('test_profiles_table_has_correct_columns', () => {
    const config = getTableConfig(profiles);
    const columns = config.columns;
    
    expect(columns).toHaveProperty('user_id');
    expect(columns).toHaveProperty('birthdate');
    expect(columns).toHaveProperty('height_cm');
    expect(columns).toHaveProperty('activity_level');
    expect(columns).toHaveProperty('experience_level');
    expect(columns).toHaveProperty('injuries');
    expect(columns).toHaveProperty('updated_at');
    
    expect(columns.user_id.dataType).toBe('string');
    expect(columns.birthdate.dataType).toBe('date');
    expect(columns.height_cm.dataType).toBe('number');
    expect(columns.activity_level.dataType).toBe('string');
    expect(columns.experience_level.dataType).toBe('string');
    expect(columns.injuries.dataType).toBe('json');
    expect(columns.updated_at.dataType).toBe('date');
  });

  test('test_profiles_user_id_is_fk_to_users', () => {
    const config = getTableConfig(profiles);
    const foreignKeys = config.foreignKeys;
    
    expect(foreignKeys.length).toBeGreaterThan(0);
    
    // Buscar FK de user_id a users
    const userIdFk = foreignKeys.find(fk => {
      const fkColumns = fk.columns.map(col => col.name);
      return fkColumns.includes('user_id');
    });
    
    expect(userIdFk).toBeDefined();
    
    if (userIdFk) {
      const referencedTable = userIdFk.reference();
      expect(referencedTable.foreignTable).toBe(users);
    }
  });
});
