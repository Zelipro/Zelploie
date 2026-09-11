-- Schéma Supabase pour Zelploie (§6 de la spec).
--
-- Cette table est UNIQUEMENT le canal de synchronisation entre les
-- appareils de Zeli. Elle n'est jamais la source de vérité consultée
-- au démarrage de l'app (ça, c'est toujours la base SQLite locale,
-- voir src/zelploie/storage/local_db.py) : Supabase ne fait que
-- pousser/recevoir les mêmes occurrences en tâche de fond.
--
-- À exécuter une fois dans l'éditeur SQL du projet Supabase (ou via
-- `supabase db push` si vous utilisez la CLI Supabase).

create table if not exists public.activity_occurrence (
    id                   text primary key,
    date                 date not null,
    debut_datetime       timestamptz not null,
    fin_datetime         timestamptz not null,
    nom_activite         text not null,
    categorie            text not null,
    schedule_block_id    text not null,
    salle                text,
    acquitte             boolean not null default false,
    acquitte_le          timestamptz,
    acquitte_par_device  text,
    updated_at           timestamptz not null default now()
);

-- Utilisé par le filtre de fenêtre glissante côté client (§4.2 : "filtré
-- sur une fenêtre glissante ... pour ne pas tout retélécharger").
create index if not exists idx_activity_occurrence_date
    on public.activity_occurrence (date);

-- ---------------------------------------------------------------------
-- Row Level Security — À LIRE ATTENTIVEMENT (Zeli, c'est pour toi).
-- ---------------------------------------------------------------------
-- Cette app est un usage strictement personnel et mono-utilisateur : il
-- n'y a pas de compte/mot de passe par appareil, seulement une clé
-- "anon" unique à ce projet Supabase, intégrée dans la configuration de
-- chacun de tes appareils (variable d'environnement, jamais commitée
-- dans le dépôt Git — voir README "Configuration Supabase").
--
-- La policy ci-dessous autorise TOUTE requête (lecture ET écriture,
-- sans restriction de ligne) dès lors qu'elle présente cette clé anon.
-- Concrètement : quiconque mettrait la main sur cette clé + l'URL du
-- projet pourrait lire et modifier l'intégralité de ton planning. Il
-- n'y a aucune protection au-delà du secret de la clé elle-même.
--
-- C'est un compromis raisonnable pour un projet perso à un seul
-- utilisateur (pas de vraie donnée sensible, pas d'exposition publique
-- de la clé), mais ce n'est PAS un niveau de sécurité "production
-- multi-utilisateur". Si un jour d'autres personnes doivent utiliser
-- la même instance, il faudra passer à une authentification Supabase
-- Auth réelle (une ligne = un user_id, policy filtrée sur auth.uid()).
alter table public.activity_occurrence enable row level security;

drop policy if exists "acces complet cle anon (usage personnel)" on public.activity_occurrence;
create policy "acces complet cle anon (usage personnel)"
    on public.activity_occurrence
    for all
    to anon
    using (true)
    with check (true);

-- Active la réplication Realtime sur cette table (nécessaire pour que
-- les abonnements .channel(...).on_postgres_changes(...) reçoivent
-- effectivement les événements). Si votre projet Supabase gère déjà
-- ses tables Realtime via le dashboard (Database > Replication), cette
-- ligne peut échouer si la table y est déjà ; dans ce cas, ignorez
-- l'erreur ou activez le toggle directement dans le dashboard à la
-- place de cette ligne.
alter publication supabase_realtime add table public.activity_occurrence;
