CREATE TABLE "agent_prompts" (
	"id" uuid PRIMARY KEY DEFAULT uuidv7() NOT NULL,
	"agent" text NOT NULL,
	"version" integer NOT NULL,
	"content" text NOT NULL,
	"status" text NOT NULL,
	"author" uuid NOT NULL,
	"notes" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "agent_prompts_agent_version_unique" UNIQUE("agent","version"),
	CONSTRAINT "status_check" CHECK ("agent_prompts"."status" IN ('draft', 'published', 'archived'))
);
--> statement-breakpoint
CREATE TABLE "llm_calls" (
	"id" uuid PRIMARY KEY DEFAULT uuidv7() NOT NULL,
	"user_id" uuid,
	"conversation_id" uuid,
	"agent" text NOT NULL,
	"model" text NOT NULL,
	"prompt_version" text,
	"tokens_in" integer NOT NULL,
	"tokens_out" integer NOT NULL,
	"cost_usd" numeric NOT NULL,
	"latency_ms" integer NOT NULL,
	"context_breakdown" jsonb NOT NULL,
	"error" text,
	"provider" text NOT NULL
);
--> statement-breakpoint
CREATE TABLE "llm_providers" (
	"id" uuid PRIMARY KEY DEFAULT uuidv7() NOT NULL,
	"name" text NOT NULL,
	"base_url" text NOT NULL,
	"secret_ref" text NOT NULL,
	"enabled" boolean NOT NULL,
	CONSTRAINT "llm_providers_name_unique" UNIQUE("name"),
	CONSTRAINT "name_check" CHECK ("llm_providers"."name" IN ('nous', 'gemini'))
);
--> statement-breakpoint
CREATE TABLE "llm_routes" (
	"agent" text PRIMARY KEY NOT NULL,
	"provider_id" uuid NOT NULL,
	"model" text NOT NULL,
	"params" jsonb,
	"fallback_provider_id" uuid,
	"fallback_model" text,
	"updated_by" uuid,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "profiles" (
	"user_id" uuid PRIMARY KEY NOT NULL,
	"birthdate" date,
	"sex" text,
	"height_cm" integer,
	"activity_level" text,
	"experience_level" text,
	"injuries" jsonb,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" uuid PRIMARY KEY DEFAULT uuidv7() NOT NULL,
	"firebase_uid" text NOT NULL,
	"email" text NOT NULL,
	"role" text DEFAULT 'user' NOT NULL,
	"locale" text DEFAULT 'es' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "users_firebase_uid_unique" UNIQUE("firebase_uid"),
	CONSTRAINT "users_email_unique" UNIQUE("email"),
	CONSTRAINT "role_check" CHECK ("users"."role" IN ('user', 'admin'))
);
--> statement-breakpoint
ALTER TABLE "llm_routes" ADD CONSTRAINT "llm_routes_provider_id_llm_providers_id_fk" FOREIGN KEY ("provider_id") REFERENCES "public"."llm_providers"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "llm_routes" ADD CONSTRAINT "llm_routes_fallback_provider_id_llm_providers_id_fk" FOREIGN KEY ("fallback_provider_id") REFERENCES "public"."llm_providers"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "profiles" ADD CONSTRAINT "profiles_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;