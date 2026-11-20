insert into tariff_ (size_, valid_from_, storage_price_per_day_, shipment_price_, overstay_price_per_day_)
values ('S', timestamptz '2026-01-01 00:00:00+01', 15.00, 39.00, 20.00),
       ('M', timestamptz '2026-01-01 00:00:00+01', 20.00, 49.00, 25.00),
       ('L', timestamptz '2026-01-01 00:00:00+01', 30.00, 59.00, 35.00);

insert into lockermat_ (code_, name_, address_, location_)
values ('KRK-GLOWNY', 'Kraków Główny', 'Kraków, ul. Pawia 5a', 'SRID=4326;POINT(19.947886 50.068424)'),
       ('KRK-LOTNISKO', 'Lotnisko Kraków-Balice', 'Kraków, ul. kpt. Mieczysława Medweckiego 1', 'SRID=4326;POINT(19.801459 50.072576)'),
       ('KRK-RYNEK', 'Rynek Główny', 'Kraków, Rynek Główny 1/3', 'SRID=4326;POINT(19.937351 50.061701)'),
       ('WAW-CENTRALNA', 'Warszawa Centralna', 'Warszawa, al. Jerozolimskie 54', 'SRID=4326;POINT(21.003160 52.228821)'),
       ('WAW-LOTNISKO', 'Lotnisko Chopina', 'Warszawa, ul. Żwirki i Wigury 1', 'SRID=4326;POINT(20.972243 52.170771)'),
       ('WAW-PKIN', 'Pałac Kultury i Nauki', 'Warszawa, pl. Defilad 1', 'SRID=4326;POINT(21.005798 52.231766)'),
       ('GDN-GLOWNY', 'Gdańsk Główny', 'Gdańsk, ul. Podwale Grodzkie 2', 'SRID=4326;POINT(18.644195 54.356435)'),
       ('GDN-LOTNISKO', 'Lotnisko Gdańsk', 'Gdańsk, ul. Juliusza Słowackiego 210A', 'SRID=4326;POINT(18.465762 54.382116)'),
       ('GDN-DLUGI-TARG', 'Długi Targ', 'Gdańsk, Długi Targ 44', 'SRID=4326;POINT(18.653371 54.348767)'),
       ('WRO-GLOWNY', 'Wrocław Główny', 'Wrocław, ul. Marszałka Józefa Piłsudskiego 105', 'SRID=4326;POINT(17.036261 51.098835)'),
       ('WRO-LOTNISKO', 'Lotnisko Wrocław', 'Wrocław, ul. Graniczna 190', 'SRID=4326;POINT(16.880565 51.109376)'),
       ('WRO-RYNEK', 'Rynek', 'Wrocław, Rynek 1', 'SRID=4326;POINT(17.030671 51.110936)');

insert into lockermat_cell_ (lockermat_id_, number_, size_)
select l.id_, n.number_, case when n.number_ <= 6 then 'S' when n.number_ <= 10 then 'M' else 'L' end
from lockermat_ l
         cross join generate_series(1, 12) as n (number_)
order by l.id_, n.number_;

insert into customer_ (keycloak_id_, phone_, company_name_, terms_version_, terms_accepted_at_)
values ('900f9895-3b4d-5e82-a35f-ad11c64f9f00', '+48500100200', null, 'demo-1', now()),
       ('a4bba234-ddf1-5dbc-bf7d-fca171bfe08f', '+48500100300', null, 'demo-1', now()),
       ('95912bb7-ca81-5398-b494-078466a4edd2', null, 'Nadawca demonstracyjny', 'demo-1', now());
