CREATE TABLE agendamento (
    id              BIGSERIAL PRIMARY KEY,
    cnes            VARCHAR(7) NOT NULL,
    especialidade   VARCHAR(60) NOT NULL,
    data_agendada   DATE NOT NULL,
    data_realizada  DATE,
    status          VARCHAR(20) NOT NULL,
    criado_em       TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agendamento_data ON agendamento (data_agendada);

INSERT INTO agendamento (cnes, especialidade, data_agendada, data_realizada, status)
VALUES
    ('2077485', 'Clinica medica',  '2026-01-08', '2026-01-08', 'REALIZADO'),
    ('2077485', 'Ortopedia',       '2026-01-09', NULL,         'CANCELADO'),
    ('2589509', 'Cardiologia',     '2026-01-12', '2026-01-12', 'REALIZADO'),
    ('2589509', 'Clinica medica',  '2026-01-15', NULL,         'AGENDADO');
