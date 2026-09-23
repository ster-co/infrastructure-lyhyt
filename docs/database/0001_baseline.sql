/*
  DRAFT schema baseline for the LYHYT customer application.

  Source: schema metadata captured from the populated SQL database discussed
  with the infrastructure work.

  Scope:
    - 36 application tables
    - primary keys, defaults, identities, unique constraints and indexes
    - foreign keys and delete actions
    - vw_projects
    - last_altered triggers

  Deliberately excluded:
    - customer data
    - dbo.MSchange_tracking_history (system-managed)
    - sys.database_firewall_rules (system view)
    - users, permissions and firewall configuration

  Execution:
    This draft uses SQLCMD GO batch separators. The future migration runner
    must either support GO or split batches before execution. It must record
    this migration's checksum and execute it only once.
*/

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

CREATE TABLE [dbo].[cc_analysis] (
    [analysis_id] int IDENTITY(1,1) NOT NULL,
    [request_id] int NOT NULL,
    [prompt_id] int NOT NULL,
    [output] nvarchar(max) NOT NULL,
    [score] decimal(5,2) NOT NULL,
    [reasoning_output] nvarchar(max) NOT NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_analysis_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_cc_analysis] PRIMARY KEY ([analysis_id])
);
GO

CREATE TABLE [dbo].[cc_categories] (
    [category_id] int IDENTITY(1,1) NOT NULL,
    [category] varchar(max) NOT NULL,
    [description] varchar(max) NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_categories_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_cc_categories] PRIMARY KEY ([category_id])
);
GO

CREATE TABLE [dbo].[cc_document_types] (
    [document_id] nvarchar(450) NOT NULL,
    [content_key] nvarchar(300) NOT NULL,
    [doc_nature] nvarchar(40) NOT NULL,
    [doc_label] nvarchar(200) NOT NULL CONSTRAINT [DF_cc_document_types_doc_label] DEFAULT (''),
    [confidence] nvarchar(10) NOT NULL CONSTRAINT [DF_cc_document_types_confidence] DEFAULT (''),
    [note] nvarchar(400) NOT NULL CONSTRAINT [DF_cc_document_types_note] DEFAULT (''),
    [classified_at] datetime2 NOT NULL CONSTRAINT [DF_cc_document_types_classified_at] DEFAULT (sysutcdatetime()),
    [synopsis] nvarchar(max) NULL,
    [chunk_count] int NULL,
    CONSTRAINT [PK__cc_docum__9666E8ACD9D3541E] PRIMARY KEY ([document_id])
);
GO

CREATE TABLE [dbo].[cc_info] (
    [info_id] int IDENTITY(1,1) NOT NULL,
    [projectrow_id] int NULL,
    [info] nvarchar(max) NULL,
    [document_type] nvarchar(50) NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_info_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_cc_info] PRIMARY KEY ([info_id])
);
GO

CREATE TABLE [dbo].[cc_lg_checkpoints] (
    [thread_id] nvarchar(200) NOT NULL,
    [checkpoint_ns] nvarchar(200) NOT NULL,
    [checkpoint_id] nvarchar(64) NOT NULL,
    [parent_checkpoint_id] nvarchar(64) NULL,
    [checkpoint_type] nvarchar(60) NOT NULL,
    [checkpoint] varbinary(max) NOT NULL,
    [metadata_type] nvarchar(60) NULL,
    [metadata] varbinary(max) NULL,
    [created_at] datetime2 NOT NULL CONSTRAINT [DF_cc_lg_checkpoints_created_at] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_cc_lg_checkpoints] PRIMARY KEY ([thread_id], [checkpoint_ns], [checkpoint_id])
);
GO

CREATE TABLE [dbo].[cc_lg_writes] (
    [thread_id] nvarchar(200) NOT NULL,
    [checkpoint_ns] nvarchar(200) NOT NULL,
    [checkpoint_id] nvarchar(64) NOT NULL,
    [task_id] nvarchar(64) NOT NULL,
    [idx] int NOT NULL,
    [channel] nvarchar(200) NOT NULL,
    [value_type] nvarchar(60) NOT NULL,
    [value] varbinary(max) NOT NULL,
    [task_path] nvarchar(400) NOT NULL CONSTRAINT [DF_cc_lg_writes_task_path] DEFAULT (''),
    CONSTRAINT [PK_cc_lg_writes] PRIMARY KEY ([thread_id], [checkpoint_ns], [checkpoint_id], [task_id], [idx])
);
GO

CREATE TABLE [dbo].[cc_locations] (
    [location_id] int IDENTITY(1,1) NOT NULL,
    [number] int NOT NULL,
    [street] nvarchar(max) NOT NULL,
    [city] nvarchar(max) NOT NULL,
    [postcode] nvarchar(max) NOT NULL,
    [partner_id] int NOT NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_locations_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_cc_locations] PRIMARY KEY ([location_id])
);
GO

CREATE TABLE [dbo].[cc_mail_origin] (
    [reply_token] nvarchar(32) NOT NULL,
    [project_id] int NULL,
    [request_ids] nvarchar(400) NULL,
    [graph_message_id] nvarchar(450) NULL,
    [conversation_id] nvarchar(450) NULL,
    [internet_message_id] nvarchar(450) NULL,
    [created_by] nvarchar(320) NULL,
    [created_at] datetime2 NOT NULL CONSTRAINT [DF_cc_mail_origin_created_at] DEFAULT (sysutcdatetime()),
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_mail_origin_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_cc_mail_origin] PRIMARY KEY ([reply_token])
);
GO

CREATE TABLE [dbo].[cc_nota] (
    [Id] int IDENTITY(1,1) NOT NULL,
    [project_id] int NOT NULL,
    [nota] varchar(max) NOT NULL,
    [version] tinyint NOT NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_nota_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_cc_nota] PRIMARY KEY ([Id])
);
GO

CREATE TABLE [dbo].[cc_offerte_summary] (
    [id] int IDENTITY(1,1) NOT NULL,
    [project_id] int NOT NULL,
    [partner_id] int NOT NULL,
    [prijs] decimal(18,2) NULL,
    [datum] date NULL,
    [opmerking] nvarchar(max) NULL,
    [folder_id] nvarchar(max) NULL,
    [folder_url] nvarchar(max) NULL,
    [MailReviewId] int NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_offerte_summary_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_cc_offerte_summary] PRIMARY KEY ([id])
);
GO

CREATE TABLE [dbo].[cc_partners] (
    [partner_id] int IDENTITY(1,1) NOT NULL,
    [company] varchar(max) NOT NULL,
    [location] varchar(max) NULL,
    [contact] varchar(max) NOT NULL,
    [Gebruiken_bij] varchar(max) NULL,
    [Opmerkingen] varchar(max) NULL,
    [Voorkeur] tinyint NULL,
    [ERP_key] int NULL,
    [engaged_partner] bit NOT NULL CONSTRAINT [DF_cc_partners_engaged_partner] DEFAULT ((0)),
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_partners_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK__cc_partn__576F1B2724FDDED4] PRIMARY KEY ([partner_id])
);
GO

CREATE TABLE [dbo].[cc_project_deadline_sync] (
    [project_id] int NOT NULL,
    [deadline_field] nvarchar(32) NOT NULL,
    [deadline_date] date NOT NULL,
    [graph_event_id] nvarchar(300) NULL,
    [reminder_sent_at] datetime2 NULL,
    [updated_at] datetime2 NOT NULL CONSTRAINT [DF_cc_project_deadline_sync_updated_at] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_cc_project_deadline_sync] PRIMARY KEY ([project_id], [deadline_field])
);
GO

CREATE TABLE [dbo].[cc_project_members] (
    [project_id] int NOT NULL,
    [user_sub] nvarchar(64) NOT NULL,
    [role] nvarchar(32) NOT NULL CONSTRAINT [DF_cc_project_members_role] DEFAULT ('owner'),
    [created_at] datetime2 NULL CONSTRAINT [DF_cc_project_members_created_at] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_cc_project_members] PRIMARY KEY ([project_id], [user_sub])
);
GO

CREATE TABLE [dbo].[cc_projects] (
    [project_id] int NOT NULL,
    [name] nvarchar(255) NULL,
    [location] nvarchar(255) NULL,
    [information_folder] nvarchar(500) NOT NULL,
    [deadline_nota] date NULL,
    [deadline_aanbesteding] date NULL,
    [deadline_quotes] date NULL,
    [information_link] nvarchar(500) NULL,
    [approved] bit NOT NULL CONSTRAINT [DF_cc_projects_approved] DEFAULT ((0)),
    [subject] ntext NULL,
    [start_bouw] nvarchar(50) NULL,
    [type_werk] nvarchar(max) NULL,
    [status] nvarchar(50) NULL,
    [schema_id] int NULL,
    [pending_manifest] nvarchar(max) NULL,
    [status_changed_at] datetime2 NULL,
    [creation_state] nvarchar(20) NULL,
    [extern_share_link] nvarchar(2048) NULL,
    [extraction_run_id] nvarchar(64) NULL,
    [extraction_run_started_at] datetime2 NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_projects_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK__cc_proje__BC799E1F5B985B21] PRIMARY KEY ([project_id])
);
GO

CREATE TABLE [dbo].[cc_projectrows] (
    [projectrow_id] int IDENTITY(1,1) NOT NULL,
    [project_id] int NOT NULL,
    [stabucode] varchar(10) NOT NULL,
    [assigned_partner_id] int NULL,
    [quote] decimal(18,2) NULL,
    [approved] bit NOT NULL CONSTRAINT [DF_cc_projectrows_approved] DEFAULT ((0)),
    [third_parties] bit NOT NULL CONSTRAINT [DF_cc_projectrows_third_parties] DEFAULT ((0)),
    [is_active] bit NOT NULL CONSTRAINT [DF_cc_projectrows_is_active] DEFAULT ((1)),
    [confidence] nvarchar(10) NULL,
    [auto_accept] bit NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_projectrows_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK__cc_proje__184F67B8C5567728] PRIMARY KEY ([projectrow_id])
);
GO

CREATE TABLE [dbo].[cc_projectsources] (
    [source_id] int IDENTITY(1,1) NOT NULL,
    [source_doc] nvarchar(max) NOT NULL,
    [page_number] int NOT NULL,
    [project_id] int NOT NULL,
    [document_id] nvarchar(128) NULL,
    [drive_id] nvarchar(256) NULL,
    [item_guid] nvarchar(64) NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_projectsources_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_cc_projectsources] PRIMARY KEY ([source_id])
);
GO

CREATE TABLE [dbo].[cc_prompting] (
    [Id] int IDENTITY(1,1) NOT NULL,
    [beschrijving] nvarchar(max) NOT NULL,
    [prompt] nvarchar(max) NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_prompting_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_dbo.cc_prompting] PRIMARY KEY ([Id])
);
GO

CREATE TABLE [dbo].[cc_prompts] (
    [prompt_id] int IDENTITY(1,1) NOT NULL,
    [werk_type] int NOT NULL,
    [item] varchar(10) NOT NULL,
    [category] int NOT NULL,
    [prompting_id] int NOT NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_prompts_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_cc_prompts] PRIMARY KEY ([prompt_id])
);
GO

CREATE TABLE [dbo].[cc_requests] (
    [request_id] int IDENTITY(1,1) NOT NULL,
    [projectrow_id] int NOT NULL,
    [project_id] int NOT NULL,
    [partner_id] int NOT NULL,
    [requested_at] date NULL,
    [last_reminded_at] date NULL,
    [quote_file] nvarchar(255) NULL,
    [status] nvarchar(20) NOT NULL CONSTRAINT [DF_cc_requests_status] DEFAULT ('open'),
    [approved] bit NOT NULL CONSTRAINT [DF_cc_requests_approved] DEFAULT ((0)),
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_requests_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK__cc_reque__18D3B90FE0763497] PRIMARY KEY ([request_id])
);
GO

CREATE TABLE [dbo].[cc_schema] (
    [schema_id] int IDENTITY(1,1) NOT NULL,
    [schema_json] json NULL,
    [isactief] bit NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_schema_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_cc_schema] PRIMARY KEY ([schema_id])
);
GO

CREATE TABLE [dbo].[cc_services] (
    [service_id] int IDENTITY(1,1) NOT NULL,
    [partner_id] int NOT NULL,
    [stabucode] varchar(10) NOT NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_services_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK__cc_servi__3E0DB8AF19B0B0E5] PRIMARY KEY ([service_id])
);
GO

CREATE TABLE [dbo].[cc_sessions] (
    [id] nvarchar(64) NOT NULL,
    [sub] nvarchar(200) NOT NULL,
    [data] nvarchar(max) NOT NULL,
    [created_at] float(53) NOT NULL,
    [last_seen] float(53) NOT NULL,
    [thread_id] nvarchar(64) NULL,
    [answered_checkpoint] nvarchar(64) NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_sessions_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_cc_sessions] PRIMARY KEY ([id])
);
GO

CREATE TABLE [dbo].[cc_share_links] (
    [token] nvarchar(64) NOT NULL,
    [project_folder] nvarchar(500) NOT NULL,
    [subfolder] nvarchar(100) NOT NULL CONSTRAINT [DF_cc_share_links_subfolder] DEFAULT ('Extern'),
    [created_by] nvarchar(200) NULL,
    [created_at] float(53) NOT NULL,
    [expires_at] float(53) NULL,
    [revoked_at] float(53) NULL,
    CONSTRAINT [PK__cc_share__CA90DA7BC16F3C1E] PRIMARY KEY ([token])
);
GO

CREATE TABLE [dbo].[cc_source_pointers] (
    [source_id] int NOT NULL,
    [chunk_id] nvarchar(512) NULL,
    [section_path] nvarchar(max) NULL,
    [analysis_cache_key] nvarchar(512) NULL,
    [analysis_engine] nvarchar(64) NULL,
    [paragraph_ordinals] nvarchar(max) NULL,
    CONSTRAINT [PK_cc_source_pointers] PRIMARY KEY ([source_id])
);
GO

CREATE TABLE [dbo].[cc_sources] (
    [source_id] int IDENTITY(1,1) NOT NULL,
    [source_doc] nvarchar(max) NULL,
    [page_number] int NULL,
    [document_type] varchar(max) NULL,
    [info_id] int NULL,
    [document_id] nvarchar(128) NULL,
    [drive_id] nvarchar(256) NULL,
    [item_guid] nvarchar(64) NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_sources_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_cc_sources] PRIMARY KEY ([source_id])
);
GO

CREATE TABLE [dbo].[cc_stabucodes] (
    [code] varchar(10) NOT NULL,
    [description] varchar(max) NOT NULL,
    [parent_code] varchar(10) NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_stabucodes_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK__cc_stabu__357D4CF89F87BF9E] PRIMARY KEY ([code])
);
GO

CREATE TABLE [dbo].[cc_test] (
    [project_id] int IDENTITY(1,1) NOT NULL,
    [name] varchar(255) NOT NULL,
    [location] varchar(max) NULL,
    [information_folder] varchar(max) NULL,
    [deadline_nota] date NULL,
    [deadline_aanbesteding] date NULL,
    [deadline_quotes] date NULL,
    [information_link] varchar(max) NULL,
    [approved] bit NOT NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_test_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK__cc_test__BC799E1F9953699F] PRIMARY KEY ([project_id])
);
GO

CREATE TABLE [dbo].[cc_werk_type] (
    [werk_type_id] int IDENTITY(1,1) NOT NULL,
    [werk_type] nvarchar(max) NOT NULL,
    [description] nvarchar(max) NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_cc_werk_type_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_cc_werk_type] PRIMARY KEY ([werk_type_id])
);
GO

CREATE TABLE [dbo].[getemail] (
    [Id] int IDENTITY(1,1) NOT NULL,
    [MailId] nvarchar(450) NOT NULL,
    [Status] nvarchar(50) NOT NULL CONSTRAINT [DF_getemail_Status] DEFAULT (N'New'),
    [Mailbox] nvarchar(320) NULL,
    [InternetMessageId] nvarchar(450) NULL,
    [ReviewId] int NULL,
    [FailureCount] int NOT NULL CONSTRAINT [DF_getemail_FailureCount] DEFAULT ((0)),
    [TrackingMailbox] nvarchar(320) NOT NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_getemail_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_getemail] PRIMARY KEY ([Id])
);
GO

CREATE TABLE [dbo].[graph_subscription] (
    [Id] int IDENTITY(1,1) NOT NULL,
    [Mailbox] nvarchar(320) NOT NULL,
    [SubscriptionId] nvarchar(64) NOT NULL,
    [Resource] nvarchar(1024) NOT NULL,
    [ExpirationDateTime] datetime2 NOT NULL,
    [CreatedAt] datetime2 NOT NULL CONSTRAINT [DF_graph_subscription_CreatedAt] DEFAULT (sysutcdatetime()),
    [UpdatedAt] datetime2 NOT NULL CONSTRAINT [DF_graph_subscription_UpdatedAt] DEFAULT (sysutcdatetime()),
    [last_altered] datetime2 NULL CONSTRAINT [DF_graph_subscription_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_graph_subscription] PRIMARY KEY ([Id])
);
GO

CREATE TABLE [dbo].[graph_sync_state] (
    [Id] int IDENTITY(1,1) NOT NULL,
    [Mailbox] nvarchar(320) NOT NULL,
    [DeltaLink] nvarchar(max) NOT NULL,
    [UpdatedAt] datetime2 NOT NULL CONSTRAINT [DF_graph_sync_state_UpdatedAt] DEFAULT (sysutcdatetime()),
    [last_altered] datetime2 NULL CONSTRAINT [DF_graph_sync_state_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_graph_sync_state] PRIMARY KEY ([Id])
);
GO

CREATE TABLE [dbo].[mail_review] (
    [Id] int IDENTITY(1,1) NOT NULL,
    [Category] nvarchar(200) NOT NULL,
    [MailText] nvarchar(max) NOT NULL,
    [Subject] nvarchar(998) NULL,
    [SenderName] nvarchar(320) NULL,
    [SenderAddress] nvarchar(320) NULL,
    [InternetMessageId] nvarchar(450) NULL,
    [ProjectId] int NULL,
    [PartnerId] int NULL,
    [Status] nvarchar(50) NOT NULL CONSTRAINT [DF_mail_review_Status] DEFAULT (N'Pending'),
    [CreatedAt] datetime2 NOT NULL CONSTRAINT [DF_mail_review_CreatedAt] DEFAULT (sysutcdatetime()),
    [ReplyToken] nvarchar(32) NULL,
    [ConversationId] nvarchar(450) NULL,
    [MailMsgBlobContainer] nvarchar(100) NULL,
    [MailMsgBlobPath] nvarchar(1024) NULL,
    [DuplicateOfReviewId] int NULL,
    [FiledSubfolder] nvarchar(400) NULL,
    [ReceivedDateTime] datetime2 NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_mail_review_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_mail_review] PRIMARY KEY ([Id])
);
GO

CREATE TABLE [dbo].[mail_review_attachment] (
    [Id] int IDENTITY(1,1) NOT NULL,
    [MailReviewId] int NOT NULL,
    [FileName] nvarchar(400) NOT NULL,
    [ContentType] nvarchar(200) NULL,
    [BlobContainer] nvarchar(100) NOT NULL,
    [BlobPath] nvarchar(1024) NOT NULL,
    [SizeBytes] bigint NULL,
    [CreatedAt] datetime2 NOT NULL CONSTRAINT [DF_mail_review_attachment_CreatedAt] DEFAULT (sysutcdatetime()),
    [last_altered] datetime2 NULL CONSTRAINT [DF_mail_review_attachment_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_mail_review_attachment] PRIMARY KEY ([Id])
);
GO

CREATE TABLE [dbo].[settings_attributes] (
    [attribute_id] int IDENTITY(1,1) NOT NULL,
    [name] nvarchar(50) NOT NULL,
    [type] nvarchar(50) NOT NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_settings_attributes_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_settings_attributes] PRIMARY KEY ([attribute_id])
);
GO

CREATE TABLE [dbo].[settings_entity] (
    [entity_id] int IDENTITY(1,1) NOT NULL,
    [type] nvarchar(50) NULL,
    [parent_entity] int NULL,
    [name] nvarchar(50) NOT NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_settings_entity_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_settings_entity] PRIMARY KEY ([entity_id])
);
GO

CREATE TABLE [dbo].[settings_value] (
    [value_id] int IDENTITY(1,1) NOT NULL,
    [entity_id] int NOT NULL,
    [attribute_id] int NOT NULL,
    [value] nvarchar(max) NOT NULL,
    [last_altered] datetime2 NULL CONSTRAINT [DF_settings_value_last_altered] DEFAULT (sysutcdatetime()),
    CONSTRAINT [PK_settings_value] PRIMARY KEY ([value_id])
);
GO

ALTER TABLE [dbo].[cc_nota]
    ADD CONSTRAINT [UQ_cc_nota_project_version] UNIQUE ([project_id], [version]);
ALTER TABLE [dbo].[cc_projectrows]
    ADD CONSTRAINT [UX_cc_projectrows_project_stabucode] UNIQUE ([project_id], [stabucode]);
ALTER TABLE [dbo].[cc_projects]
    ADD CONSTRAINT [UX_cc_projects_information_folder] UNIQUE ([information_folder]);
ALTER TABLE [dbo].[cc_services]
    ADD CONSTRAINT [UX_cc_services_partner_id_stabucode] UNIQUE ([partner_id], [stabucode]);
ALTER TABLE [dbo].[cc_test]
    ADD CONSTRAINT [UQ__cc_test__72E12F1B6CD2900C] UNIQUE ([name]);
ALTER TABLE [dbo].[getemail]
    ADD CONSTRAINT [UQ_getemail_TrackingMailbox_MailId] UNIQUE ([TrackingMailbox], [MailId]);
ALTER TABLE [dbo].[graph_subscription]
    ADD CONSTRAINT [UQ_graph_subscription_Mailbox] UNIQUE ([Mailbox]);
ALTER TABLE [dbo].[graph_sync_state]
    ADD CONSTRAINT [UQ_graph_sync_state_Mailbox] UNIQUE ([Mailbox]);
ALTER TABLE [dbo].[mail_review]
    ADD CONSTRAINT [UQ_mail_review_InternetMessageId] UNIQUE ([InternetMessageId]);
GO

CREATE INDEX [IX_cc_lg_checkpoints_created_at]
    ON [dbo].[cc_lg_checkpoints] ([created_at], [thread_id]);
CREATE INDEX [IX_cc_offerte_summary_MailReviewId]
    ON [dbo].[cc_offerte_summary] ([MailReviewId]);
CREATE INDEX [IX_cc_project_members_user]
    ON [dbo].[cc_project_members] ([user_sub]);
CREATE INDEX [IX_cc_requests_partner_id_project_id]
    ON [dbo].[cc_requests] ([partner_id], [project_id])
    INCLUDE ([projectrow_id], [requested_at], [last_reminded_at], [quote_file], [status], [approved]);
CREATE INDEX [IX_cc_requests_project_id_partner_id]
    ON [dbo].[cc_requests] ([project_id], [partner_id])
    INCLUDE ([projectrow_id], [status], [approved]);
CREATE INDEX [IX_cc_requests_projectrow_id_partner_id]
    ON [dbo].[cc_requests] ([projectrow_id], [partner_id])
    INCLUDE ([project_id], [requested_at], [last_reminded_at], [quote_file], [status], [approved]);
CREATE INDEX [IX_cc_services_stabucode_partner_id]
    ON [dbo].[cc_services] ([stabucode], [partner_id]);
CREATE INDEX [IX_cc_sessions_created_at]
    ON [dbo].[cc_sessions] ([created_at]);
CREATE INDEX [IX_cc_sessions_last_seen]
    ON [dbo].[cc_sessions] ([last_seen]);
CREATE INDEX [IX_cc_source_pointers_source_id]
    ON [dbo].[cc_source_pointers] ([source_id]);
CREATE INDEX [IX_getemail_InternetMessageId]
    ON [dbo].[getemail] ([InternetMessageId]);
CREATE INDEX [IX_getemail_ReviewId]
    ON [dbo].[getemail] ([ReviewId]);
CREATE INDEX [IX_graph_subscription_SubscriptionId]
    ON [dbo].[graph_subscription] ([SubscriptionId]);
CREATE INDEX [IX_mail_review_ConversationId]
    ON [dbo].[mail_review] ([ConversationId]);
CREATE INDEX [IX_mail_review_DuplicateOfReviewId]
    ON [dbo].[mail_review] ([DuplicateOfReviewId]);
CREATE INDEX [IX_mail_review_ReplyToken]
    ON [dbo].[mail_review] ([ReplyToken]);
CREATE INDEX [IX_mail_review_Status]
    ON [dbo].[mail_review] ([Status]);
CREATE INDEX [IX_mail_review_attachment_MailReviewId]
    ON [dbo].[mail_review_attachment] ([MailReviewId]);
GO

ALTER TABLE [dbo].[cc_analysis] WITH CHECK
    ADD CONSTRAINT [FK_cc_analysis_cc_prompts]
    FOREIGN KEY ([prompt_id]) REFERENCES [dbo].[cc_prompts] ([prompt_id])
    ON DELETE CASCADE;
ALTER TABLE [dbo].[cc_analysis] CHECK CONSTRAINT [FK_cc_analysis_cc_prompts];

ALTER TABLE [dbo].[cc_analysis] WITH CHECK
    ADD CONSTRAINT [FK_cc_analysis_cc_requests]
    FOREIGN KEY ([request_id]) REFERENCES [dbo].[cc_requests] ([request_id])
    ON DELETE CASCADE;
ALTER TABLE [dbo].[cc_analysis] CHECK CONSTRAINT [FK_cc_analysis_cc_requests];

ALTER TABLE [dbo].[cc_info] WITH CHECK
    ADD CONSTRAINT [FK_cc_info_cc_projectrows]
    FOREIGN KEY ([projectrow_id]) REFERENCES [dbo].[cc_projectrows] ([projectrow_id])
    ON DELETE CASCADE;
ALTER TABLE [dbo].[cc_info] CHECK CONSTRAINT [FK_cc_info_cc_projectrows];

ALTER TABLE [dbo].[cc_locations] WITH CHECK
    ADD CONSTRAINT [FK_cc_locations_cc_partners]
    FOREIGN KEY ([partner_id]) REFERENCES [dbo].[cc_partners] ([partner_id])
    ON DELETE CASCADE;
ALTER TABLE [dbo].[cc_locations] CHECK CONSTRAINT [FK_cc_locations_cc_partners];

ALTER TABLE [dbo].[cc_nota] WITH CHECK
    ADD CONSTRAINT [FK_cc_nota_cc_projects]
    FOREIGN KEY ([project_id]) REFERENCES [dbo].[cc_projects] ([project_id])
    ON DELETE CASCADE;
ALTER TABLE [dbo].[cc_nota] CHECK CONSTRAINT [FK_cc_nota_cc_projects];

ALTER TABLE [dbo].[cc_offerte_summary] WITH CHECK
    ADD CONSTRAINT [FK_cc_offerte_summary_cc_partners]
    FOREIGN KEY ([partner_id]) REFERENCES [dbo].[cc_partners] ([partner_id])
    ON DELETE CASCADE;
ALTER TABLE [dbo].[cc_offerte_summary] CHECK CONSTRAINT [FK_cc_offerte_summary_cc_partners];

ALTER TABLE [dbo].[cc_offerte_summary] WITH CHECK
    ADD CONSTRAINT [FK_cc_offerte_summary_cc_projects]
    FOREIGN KEY ([project_id]) REFERENCES [dbo].[cc_projects] ([project_id])
    ON DELETE CASCADE;
ALTER TABLE [dbo].[cc_offerte_summary] CHECK CONSTRAINT [FK_cc_offerte_summary_cc_projects];

ALTER TABLE [dbo].[cc_offerte_summary] WITH CHECK
    ADD CONSTRAINT [FK_cc_offerte_summary_mail_review]
    FOREIGN KEY ([MailReviewId]) REFERENCES [dbo].[mail_review] ([Id]);
ALTER TABLE [dbo].[cc_offerte_summary] CHECK CONSTRAINT [FK_cc_offerte_summary_mail_review];

ALTER TABLE [dbo].[cc_project_deadline_sync] WITH CHECK
    ADD CONSTRAINT [FK_cc_project_deadline_sync_cc_projects]
    FOREIGN KEY ([project_id]) REFERENCES [dbo].[cc_projects] ([project_id])
    ON DELETE CASCADE;
ALTER TABLE [dbo].[cc_project_deadline_sync] CHECK CONSTRAINT [FK_cc_project_deadline_sync_cc_projects];

ALTER TABLE [dbo].[cc_projectrows] WITH CHECK
    ADD CONSTRAINT [FK_cc_projectrows_partners]
    FOREIGN KEY ([assigned_partner_id]) REFERENCES [dbo].[cc_partners] ([partner_id]);
ALTER TABLE [dbo].[cc_projectrows] CHECK CONSTRAINT [FK_cc_projectrows_partners];

ALTER TABLE [dbo].[cc_projectrows] WITH CHECK
    ADD CONSTRAINT [FK_cc_projectrows_projects]
    FOREIGN KEY ([project_id]) REFERENCES [dbo].[cc_projects] ([project_id])
    ON DELETE CASCADE;
ALTER TABLE [dbo].[cc_projectrows] CHECK CONSTRAINT [FK_cc_projectrows_projects];

ALTER TABLE [dbo].[cc_projectrows] WITH CHECK
    ADD CONSTRAINT [FK_cc_projectrows_stabucodes]
    FOREIGN KEY ([stabucode]) REFERENCES [dbo].[cc_stabucodes] ([code]);
ALTER TABLE [dbo].[cc_projectrows] CHECK CONSTRAINT [FK_cc_projectrows_stabucodes];

ALTER TABLE [dbo].[cc_projects] WITH CHECK
    ADD CONSTRAINT [FK_cc_projects_cc_schema]
    FOREIGN KEY ([schema_id]) REFERENCES [dbo].[cc_schema] ([schema_id])
    ON DELETE SET NULL;
ALTER TABLE [dbo].[cc_projects] CHECK CONSTRAINT [FK_cc_projects_cc_schema];

ALTER TABLE [dbo].[cc_projectsources] WITH CHECK
    ADD CONSTRAINT [FK_cc_projectsources_cc_projects]
    FOREIGN KEY ([project_id]) REFERENCES [dbo].[cc_projects] ([project_id])
    ON DELETE CASCADE;
ALTER TABLE [dbo].[cc_projectsources] CHECK CONSTRAINT [FK_cc_projectsources_cc_projects];

ALTER TABLE [dbo].[cc_prompts] WITH CHECK
    ADD CONSTRAINT [FK_cc_prompts_cc_categories]
    FOREIGN KEY ([category]) REFERENCES [dbo].[cc_categories] ([category_id])
    ON DELETE CASCADE;
ALTER TABLE [dbo].[cc_prompts] CHECK CONSTRAINT [FK_cc_prompts_cc_categories];

ALTER TABLE [dbo].[cc_prompts] WITH CHECK
    ADD CONSTRAINT [FK_cc_prompts_cc_stabucodes]
    FOREIGN KEY ([item]) REFERENCES [dbo].[cc_stabucodes] ([code]);
ALTER TABLE [dbo].[cc_prompts] CHECK CONSTRAINT [FK_cc_prompts_cc_stabucodes];

ALTER TABLE [dbo].[cc_prompts] WITH CHECK
    ADD CONSTRAINT [FK_cc_prompts_cc_werk_type]
    FOREIGN KEY ([werk_type]) REFERENCES [dbo].[cc_werk_type] ([werk_type_id])
    ON DELETE CASCADE;
ALTER TABLE [dbo].[cc_prompts] CHECK CONSTRAINT [FK_cc_prompts_cc_werk_type];

ALTER TABLE [dbo].[cc_prompts] WITH CHECK
    ADD CONSTRAINT [FK_cc_prompts_dbo.cc_prompting]
    FOREIGN KEY ([prompting_id]) REFERENCES [dbo].[cc_prompting] ([Id]);
ALTER TABLE [dbo].[cc_prompts] CHECK CONSTRAINT [FK_cc_prompts_dbo.cc_prompting];

ALTER TABLE [dbo].[cc_requests] WITH CHECK
    ADD CONSTRAINT [FK_requests_partner]
    FOREIGN KEY ([partner_id]) REFERENCES [dbo].[cc_partners] ([partner_id]);
ALTER TABLE [dbo].[cc_requests] CHECK CONSTRAINT [FK_requests_partner];

ALTER TABLE [dbo].[cc_requests] WITH CHECK
    ADD CONSTRAINT [FK_requests_project]
    FOREIGN KEY ([project_id]) REFERENCES [dbo].[cc_projects] ([project_id])
    ON DELETE CASCADE;
ALTER TABLE [dbo].[cc_requests] CHECK CONSTRAINT [FK_requests_project];

ALTER TABLE [dbo].[cc_requests] WITH CHECK
    ADD CONSTRAINT [FK_requests_projectrow]
    FOREIGN KEY ([projectrow_id]) REFERENCES [dbo].[cc_projectrows] ([projectrow_id]);
ALTER TABLE [dbo].[cc_requests] CHECK CONSTRAINT [FK_requests_projectrow];

ALTER TABLE [dbo].[cc_services] WITH CHECK
    ADD CONSTRAINT [FK__cc_servic__partn__3493CFA7]
    FOREIGN KEY ([partner_id]) REFERENCES [dbo].[cc_partners] ([partner_id])
    ON DELETE CASCADE;
ALTER TABLE [dbo].[cc_services] CHECK CONSTRAINT [FK__cc_servic__partn__3493CFA7];

ALTER TABLE [dbo].[cc_services] WITH CHECK
    ADD CONSTRAINT [FK__cc_servic__stabu__32AB8735]
    FOREIGN KEY ([stabucode]) REFERENCES [dbo].[cc_stabucodes] ([code]);
ALTER TABLE [dbo].[cc_services] CHECK CONSTRAINT [FK__cc_servic__stabu__32AB8735];

ALTER TABLE [dbo].[cc_services] WITH CHECK
    ADD CONSTRAINT [FK__cc_servic__stabu__339FAB6E]
    FOREIGN KEY ([stabucode]) REFERENCES [dbo].[cc_stabucodes] ([code]);
ALTER TABLE [dbo].[cc_services] CHECK CONSTRAINT [FK__cc_servic__stabu__339FAB6E];

ALTER TABLE [dbo].[cc_source_pointers] WITH CHECK
    ADD CONSTRAINT [FK_cc_source_pointers_cc_sources]
    FOREIGN KEY ([source_id]) REFERENCES [dbo].[cc_sources] ([source_id])
    ON DELETE CASCADE;
ALTER TABLE [dbo].[cc_source_pointers] CHECK CONSTRAINT [FK_cc_source_pointers_cc_sources];

ALTER TABLE [dbo].[cc_sources] WITH CHECK
    ADD CONSTRAINT [FK_cc_sources_cc_info]
    FOREIGN KEY ([info_id]) REFERENCES [dbo].[cc_info] ([info_id])
    ON DELETE CASCADE;
ALTER TABLE [dbo].[cc_sources] CHECK CONSTRAINT [FK_cc_sources_cc_info];

ALTER TABLE [dbo].[cc_stabucodes] WITH CHECK
    ADD CONSTRAINT [FK__cc_stabuc__paren__367C1819]
    FOREIGN KEY ([parent_code]) REFERENCES [dbo].[cc_stabucodes] ([code]);
ALTER TABLE [dbo].[cc_stabucodes] CHECK CONSTRAINT [FK__cc_stabuc__paren__367C1819];

ALTER TABLE [dbo].[cc_stabucodes] WITH CHECK
    ADD CONSTRAINT [FK__cc_stabuc__paren__37703C52]
    FOREIGN KEY ([parent_code]) REFERENCES [dbo].[cc_stabucodes] ([code]);
ALTER TABLE [dbo].[cc_stabucodes] CHECK CONSTRAINT [FK__cc_stabuc__paren__37703C52];

ALTER TABLE [dbo].[getemail] WITH CHECK
    ADD CONSTRAINT [FK_getemail_mail_review]
    FOREIGN KEY ([ReviewId]) REFERENCES [dbo].[mail_review] ([Id])
    ON DELETE SET NULL;
ALTER TABLE [dbo].[getemail] CHECK CONSTRAINT [FK_getemail_mail_review];

ALTER TABLE [dbo].[mail_review] WITH CHECK
    ADD CONSTRAINT [FK_mail_review_cc_partners]
    FOREIGN KEY ([PartnerId]) REFERENCES [dbo].[cc_partners] ([partner_id]);
ALTER TABLE [dbo].[mail_review] CHECK CONSTRAINT [FK_mail_review_cc_partners];

ALTER TABLE [dbo].[mail_review] WITH CHECK
    ADD CONSTRAINT [FK_mail_review_cc_projects]
    FOREIGN KEY ([ProjectId]) REFERENCES [dbo].[cc_projects] ([project_id]);
ALTER TABLE [dbo].[mail_review] CHECK CONSTRAINT [FK_mail_review_cc_projects];

ALTER TABLE [dbo].[mail_review] WITH CHECK
    ADD CONSTRAINT [FK_mail_review_DuplicateOfReviewId]
    FOREIGN KEY ([DuplicateOfReviewId]) REFERENCES [dbo].[mail_review] ([Id]);
ALTER TABLE [dbo].[mail_review] CHECK CONSTRAINT [FK_mail_review_DuplicateOfReviewId];

ALTER TABLE [dbo].[mail_review_attachment] WITH CHECK
    ADD CONSTRAINT [FK_mail_review_attachment_mail_review]
    FOREIGN KEY ([MailReviewId]) REFERENCES [dbo].[mail_review] ([Id])
    ON DELETE CASCADE;
ALTER TABLE [dbo].[mail_review_attachment] CHECK CONSTRAINT [FK_mail_review_attachment_mail_review];

ALTER TABLE [dbo].[settings_entity] WITH CHECK
    ADD CONSTRAINT [FK_settings_entity_settings_entity]
    FOREIGN KEY ([parent_entity]) REFERENCES [dbo].[settings_entity] ([entity_id]);
ALTER TABLE [dbo].[settings_entity] CHECK CONSTRAINT [FK_settings_entity_settings_entity];

ALTER TABLE [dbo].[settings_value] WITH CHECK
    ADD CONSTRAINT [FK_settings_value_settings_attributes]
    FOREIGN KEY ([attribute_id]) REFERENCES [dbo].[settings_attributes] ([attribute_id]);
ALTER TABLE [dbo].[settings_value] CHECK CONSTRAINT [FK_settings_value_settings_attributes];

ALTER TABLE [dbo].[settings_value] WITH CHECK
    ADD CONSTRAINT [FK_settings_value_settings_entity]
    FOREIGN KEY ([entity_id]) REFERENCES [dbo].[settings_entity] ([entity_id]);
ALTER TABLE [dbo].[settings_value] CHECK CONSTRAINT [FK_settings_value_settings_entity];
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

CREATE VIEW [dbo].[vw_projects] AS
SELECT
    [project_id],
    [name],
    [information_folder],
    [location],
    [deadline_nota],
    [deadline_aanbesteding],
    [deadline_quotes],
    [information_link],
    [approved],
    CONCAT(
        'Project ID: ', CAST([project_id] AS varchar(20)),
        '| Name: ', [name],
        '| Information Folder: ', [information_folder],
        '| Location: ', [location],
        '| Deadline nota van inlichtingen: ', [deadline_nota],
        '| Deadline aanbesteding: ', [deadline_aanbesteding],
        '| Deadline offertes: ', [deadline_quotes],
        '| Informatie link: ', [information_link],
        '| Approved: ', [approved]
    ) AS [project_text]
FROM [dbo].[cc_projects]
WHERE [name] IS NOT NULL;
GO

CREATE TRIGGER [dbo].[TR_cc_analysis_last_altered] ON [dbo].[cc_analysis] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_analysis] AS t
      INNER JOIN inserted AS i ON t.[analysis_id] = i.[analysis_id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_categories_last_altered] ON [dbo].[cc_categories] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_categories] AS t
      INNER JOIN inserted AS i ON t.[category_id] = i.[category_id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_info_last_altered] ON [dbo].[cc_info] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_info] AS t
      INNER JOIN inserted AS i ON t.[info_id] = i.[info_id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_locations_last_altered] ON [dbo].[cc_locations] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_locations] AS t
      INNER JOIN inserted AS i ON t.[location_id] = i.[location_id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_mail_origin_last_altered] ON [dbo].[cc_mail_origin] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_mail_origin] AS t
      INNER JOIN inserted AS i ON t.[reply_token] = i.[reply_token];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_nota_last_altered] ON [dbo].[cc_nota] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_nota] AS t
      INNER JOIN inserted AS i ON t.[Id] = i.[Id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_offerte_summary_last_altered] ON [dbo].[cc_offerte_summary] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_offerte_summary] AS t
      INNER JOIN inserted AS i ON t.[id] = i.[id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_partners_last_altered] ON [dbo].[cc_partners] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_partners] AS t
      INNER JOIN inserted AS i ON t.[partner_id] = i.[partner_id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_projectrows_last_altered] ON [dbo].[cc_projectrows] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_projectrows] AS t
      INNER JOIN inserted AS i ON t.[projectrow_id] = i.[projectrow_id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_projects_last_altered] ON [dbo].[cc_projects] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_projects] AS t
      INNER JOIN inserted AS i ON t.[project_id] = i.[project_id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_projectsources_last_altered] ON [dbo].[cc_projectsources] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_projectsources] AS t
      INNER JOIN inserted AS i ON t.[source_id] = i.[source_id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_prompting_last_altered] ON [dbo].[cc_prompting] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_prompting] AS t
      INNER JOIN inserted AS i ON t.[Id] = i.[Id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_prompts_last_altered] ON [dbo].[cc_prompts] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_prompts] AS t
      INNER JOIN inserted AS i ON t.[prompt_id] = i.[prompt_id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_requests_last_altered] ON [dbo].[cc_requests] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_requests] AS t
      INNER JOIN inserted AS i ON t.[request_id] = i.[request_id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_schema_last_altered] ON [dbo].[cc_schema] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_schema] AS t
      INNER JOIN inserted AS i ON t.[schema_id] = i.[schema_id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_services_last_altered] ON [dbo].[cc_services] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_services] AS t
      INNER JOIN inserted AS i ON t.[service_id] = i.[service_id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_sessions_last_altered] ON [dbo].[cc_sessions] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_sessions] AS t
      INNER JOIN inserted AS i ON t.[id] = i.[id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_sources_last_altered] ON [dbo].[cc_sources] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_sources] AS t
      INNER JOIN inserted AS i ON t.[source_id] = i.[source_id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_stabucodes_last_altered] ON [dbo].[cc_stabucodes] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_stabucodes] AS t
      INNER JOIN inserted AS i ON t.[code] = i.[code];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_test_last_altered] ON [dbo].[cc_test] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_test] AS t
      INNER JOIN inserted AS i ON t.[project_id] = i.[project_id];
END;
GO

CREATE TRIGGER [dbo].[TR_cc_werk_type_last_altered] ON [dbo].[cc_werk_type] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[cc_werk_type] AS t
      INNER JOIN inserted AS i ON t.[werk_type_id] = i.[werk_type_id];
END;
GO

CREATE TRIGGER [dbo].[TR_getemail_last_altered] ON [dbo].[getemail] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[getemail] AS t
      INNER JOIN inserted AS i ON t.[Id] = i.[Id];
END;
GO

CREATE TRIGGER [dbo].[TR_graph_subscription_last_altered] ON [dbo].[graph_subscription] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[graph_subscription] AS t
      INNER JOIN inserted AS i ON t.[Id] = i.[Id];
END;
GO

CREATE TRIGGER [dbo].[TR_graph_sync_state_last_altered] ON [dbo].[graph_sync_state] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[graph_sync_state] AS t
      INNER JOIN inserted AS i ON t.[Id] = i.[Id];
END;
GO

CREATE TRIGGER [dbo].[TR_mail_review_last_altered] ON [dbo].[mail_review] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[mail_review] AS t
      INNER JOIN inserted AS i ON t.[Id] = i.[Id];
END;
GO

CREATE TRIGGER [dbo].[TR_mail_review_attachment_last_altered] ON [dbo].[mail_review_attachment] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[mail_review_attachment] AS t
      INNER JOIN inserted AS i ON t.[Id] = i.[Id];
END;
GO

CREATE TRIGGER [dbo].[TR_settings_attributes_last_altered] ON [dbo].[settings_attributes] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[settings_attributes] AS t
      INNER JOIN inserted AS i ON t.[attribute_id] = i.[attribute_id];
END;
GO

CREATE TRIGGER [dbo].[TR_settings_entity_last_altered] ON [dbo].[settings_entity] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[settings_entity] AS t
      INNER JOIN inserted AS i ON t.[entity_id] = i.[entity_id];
END;
GO

CREATE TRIGGER [dbo].[TR_settings_value_last_altered] ON [dbo].[settings_value] AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) RETURN;
    UPDATE t
       SET t.[last_altered] = sysutcdatetime()
      FROM dbo.[settings_value] AS t
      INNER JOIN inserted AS i ON t.[value_id] = i.[value_id];
END;
GO
