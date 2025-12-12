# Database Migrations

This directory contains SQL migration files for setting up the Quiz Bot database schema in Supabase.

## Migration Order

**IMPORTANT**: Run migrations in this exact order:

1. `001_initial_schema.sql` - Creates all tables, indexes, and triggers
2. `002_security_policies.sql` - **REQUIRED** - Enables Row Level Security and creates security policies

## Setup Instructions

### 1. Create a Supabase Project

1. Go to [Supabase](https://supabase.com)
2. Create a new project
3. Note your project URL and API keys

### 2. Configure Environment Variables

Add these to your `.env` file:

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

**CRITICAL SECURITY NOTE**: 
- Use `SUPABASE_SERVICE_ROLE_KEY` (service role key) for bot operations
- **DO NOT** use the anon key - it will be blocked by Row Level Security
- The service role key bypasses RLS but should only be used server-side

### 3. Run Migrations

#### Option A: Using Supabase SQL Editor (Recommended)

1. Go to your Supabase Dashboard
2. Navigate to **SQL Editor**
3. **First**, open and run `001_initial_schema.sql`
   - Copy the entire contents
   - Paste into SQL Editor
   - Click **Run**
4. **Then**, open and run `002_security_policies.sql`
   - Copy the entire contents
   - Paste into SQL Editor
   - Click **Run**
   - This enables security features

#### Option B: Using psql (Advanced)

If you have `psql` installed and database connection string:

```bash
psql "postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres" -f migrations/001_initial_schema.sql
psql "postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres" -f migrations/002_security_policies.sql
```

### 4. Verify Migration

After running migrations, verify:

1. **Tables Created**: Go to **Table Editor** - you should see:
   - `users`
   - `chapters`
   - `questions`
   - `quiz_attempts`
   - `user_question_history`
   - `active_quizzes`
   - `rate_limits` (optional)
   - `security_audit_log` (optional)

2. **RLS Enabled**: Go to **Table Editor** → Select any table → **Settings** → Check "RLS enabled"

3. **Policies Created**: Go to **Authentication** → **Policies** → Verify policies exist

4. **Functions Created**: Go to **Database** → **Functions** → Verify:
   - `get_user_stats`
   - `get_leaderboard`
   - `record_quiz_attempt`

## Security Features

After running `002_security_policies.sql`:

- ✅ Row Level Security (RLS) enabled on all tables
- ✅ Security policies restrict access
- ✅ Secure functions for common operations
- ✅ Public access revoked
- ✅ Input validation in functions
- ✅ Audit logging available

See `SECURITY_GUIDE.md` for detailed security information.

## Adding New Migrations

1. Create a new file: `003_description.sql`
2. Number them sequentially
3. Include only the changes (ALTER TABLE, CREATE INDEX, etc.)
4. Document what the migration does in comments
5. Test in development first

## Rollback

To rollback a migration, you'll need to create a reverse migration file. For example:
- `001_initial_schema.sql` creates tables
- `001_initial_schema_rollback.sql` would drop tables

**WARNING**: Rolling back security policies (`002_security_policies.sql`) will disable security features. Only do this if absolutely necessary.

## Troubleshooting

### "Access denied" errors
- **Cause**: Using anon key instead of service role key
- **Fix**: Use `SUPABASE_SERVICE_ROLE_KEY` in `.env`

### "Function does not exist" errors
- **Cause**: Security migration (`002_security_policies.sql`) not run
- **Fix**: Run the security migration

### "RLS policy violation" errors
- **Cause**: Accessing data without proper permissions
- **Fix**: Ensure using service role key for bot operations

### Tables not created
- **Cause**: First migration not run
- **Fix**: Run `001_initial_schema.sql` first

## Notes

- Always backup your database before running migrations in production
- Test migrations in a development environment first
- Supabase uses PostgreSQL, so all SQL is PostgreSQL-compatible
- RLS is critical for security - don't disable it
- Service role key is required for bot operations

## Support

- [Supabase Documentation](https://supabase.com/docs)
- [Supabase Discord](https://discord.supabase.com)
- See `SECURITY_GUIDE.md` for security questions
