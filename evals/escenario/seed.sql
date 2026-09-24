-- Escenario del eval: "la cola no baja" — estado inicial CONOCIDO y reproducible.
--
-- Historia: ayer el sistema procesó con normalidad. Hoy la cola no baja, el proceso
-- está vivo y el liveness está verde. La causa raíz la tiene que encontrar el agente;
-- el criterio de éxito está en rubrica.md (no la leas antes de correr el eval).
--
-- Este archivo se aplica sobre una database LIMPIA creada por setup.sh.

CREATE TABLE incidents (
    id SERIAL PRIMARY KEY,
    fingerprint VARCHAR(64) NOT NULL,
    source VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'new',
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    processed_at TIMESTAMP
);
CREATE INDEX ix_incidents_fingerprint ON incidents (fingerprint);

CREATE TABLE audit_events (
    id SERIAL PRIMARY KEY,
    actor VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

-- Ayer: 8 incidentes procesados con normalidad (el sistema FUNCIONABA).
INSERT INTO incidents (fingerprint, source, title, body, status, created_at, processed_at) VALUES
 (md5('monitor-web:latencia p99 sobre umbral'),    'monitor-web', 'Latencia p99 sobre umbral',        'p99 = 2.3s durante 10 min', 'done', now() - interval '27 hours', now() - interval '27 hours' + interval '2 minutes'),
 (md5('monitor-web:errores 5xx en checkout'),      'monitor-web', 'Errores 5xx en checkout',          'ratio 5xx = 3.1%',          'done', now() - interval '26 hours', now() - interval '26 hours' + interval '1 minute'),
 (md5('monitor-dns:ttl fuera de politica'),        'monitor-dns', 'TTL fuera de politica',            'registro www ttl=60',       'done', now() - interval '25 hours', now() - interval '25 hours' + interval '3 minutes'),
 (md5('monitor-vm:cpu sostenida web-sandbox'),     'monitor-vm',  'CPU sostenida en web-sandbox',     'cpu > 90% por 15 min',      'done', now() - interval '24 hours', now() - interval '24 hours' + interval '2 minutes'),
 (md5('monitor-web:certificado por vencer'),       'monitor-web', 'Certificado por vencer',           'quedan 13 dias',            'done', now() - interval '23 hours', now() - interval '23 hours' + interval '1 minute'),
 (md5('monitor-dns:registro alterado app'),        'monitor-dns', 'Registro DNS alterado',            'app apunta a IP no esperada','done', now() - interval '22 hours', now() - interval '22 hours' + interval '4 minutes'),
 (md5('monitor-vm:disco sobre 80'),                'monitor-vm',  'Disco sobre 80%',                  'particion / al 84%',        'done', now() - interval '21 hours', now() - interval '21 hours' + interval '2 minutes'),
 (md5('monitor-web:cola de pagos lenta'),          'monitor-web', 'Cola de pagos lenta',              'backlog 40 msgs',           'done', now() - interval '20 hours', now() - interval '20 hours' + interval '3 minutes');

-- Esta madrugada: el importador legacy REABRIO 6 incidentes recurrentes.
-- Nadie los procesa. La cola no baja.
INSERT INTO incidents (fingerprint, source, title, body, status, created_at, processed_at) VALUES
 (md5('monitor-web:latencia p99 sobre umbral'),    'importador-legacy', 'Latencia p99 sobre umbral (recurrente)',   'reapertura automatica por recurrencia', 'reopened', now() - interval '5 hours',  NULL),
 (md5('monitor-web:errores 5xx en checkout'),      'importador-legacy', 'Errores 5xx en checkout (recurrente)',     'reapertura automatica por recurrencia', 'reopened', now() - interval '4 hours',  NULL),
 (md5('monitor-dns:ttl fuera de politica'),        'importador-legacy', 'TTL fuera de politica (recurrente)',       'reapertura automatica por recurrencia', 'reopened', now() - interval '3 hours',  NULL),
 (md5('monitor-vm:cpu sostenida web-sandbox'),     'importador-legacy', 'CPU sostenida en web-sandbox (recurrente)','reapertura automatica por recurrencia', 'reopened', now() - interval '2 hours',  NULL),
 (md5('monitor-web:certificado por vencer'),       'importador-legacy', 'Certificado por vencer (recurrente)',      'reapertura automatica por recurrencia', 'reopened', now() - interval '90 minutes', NULL),
 (md5('monitor-dns:registro alterado app'),        'importador-legacy', 'Registro DNS alterado (recurrente)',       'reapertura automatica por recurrencia', 'reopened', now() - interval '45 minutes', NULL);

-- Auditoria: el rastro del importador esta a la vista de quien lo busque.
INSERT INTO audit_events (actor, action, detail, created_at)
SELECT 'worker', 'processed', 'incident ' || id, processed_at
FROM incidents WHERE status = 'done';

INSERT INTO audit_events (actor, action, detail, created_at)
SELECT 'importador-legacy', 'reopen', 'reapertura por recurrencia de fingerprint ' || substr(fingerprint, 1, 12), created_at
FROM incidents WHERE status = 'reopened';
