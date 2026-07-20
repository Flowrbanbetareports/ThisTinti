# Profilo opzionale Supabase/PostgreSQL

ThisTinti può usare il PostgreSQL di Supabase tramite una connessione **solo server-side** impostata in `THISTINTI_DATABASE_URL`.

La build non richiede Supabase Auth, `supabase-js`, chiavi publishable o service-role nel frontend. FastAPI è l'unico punto di accesso ai dati.

## Procedura

1. creare un progetto dedicato a ThisTinti;
2. recuperare una connection string PostgreSQL per il backend;
3. conservarla nei secret dell'ambiente;
4. impostare `THISTINTI_AUTO_CREATE_SCHEMA=false`;
5. eseguire `alembic upgrade head`;
6. verificare `/api/readiness`;
7. non esporre le tabelle alla Data API se non necessario;
8. usare storage privato separato per i documenti.

## RLS

L'isolamento tenant è applicato dal backend. Se le tabelle vengono esposte anche tramite Data API, abilitare RLS su ogni tabella esposta e creare policy di autorizzazione reali. `TO authenticated` da solo non separa i tenant.

Non usare `user_metadata` modificabile dall'utente per autorizzare. Non inserire mai service-role o password database nel JavaScript pubblico.

## Stato di verifica

Lo schema PostgreSQL è generato offline in `docs/postgresql-schema.sql`. In questo ambiente non è stato creato un progetto Supabase dedicato né sostenuto alcun costo. Il collaudo live va eseguito sul progetto scelto dal gestore.
