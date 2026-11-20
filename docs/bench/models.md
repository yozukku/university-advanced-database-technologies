# Benchmark data models

[The PostgreSQL schema](../design/schema.sql) defines the 13 logical tables, their column names and their constraints. The generator assigns the logical ids in Parquet. Each engine loads a representation of those same records, and verification reconstructs the canonical tables before comparing hashes. MySQL retains the names and the rows of all 13 tables. A MongoDB subdocument and a Neo4j node or label can represent a logical row.

## Table mapping

| Canonical table | MongoDB collection or path | Neo4j label |
|---|---|---|
| `lockermat_` | `lockermats` | `Lockermat` |
| `lockermat_opening_hours_` | `lockermats.openingHours[]` | `OpeningHours` |
| `lockermat_cell_` | `lockermats.cells[]` | `Cell` |
| `tariff_` | `tariffs` | `Tariff` |
| `customer_` | `customers` | `Customer` |
| `order_` | `orders` | `Order` |
| `reservation_` | `orders.reservations[]` | `Reservation` |
| `shipment_` | `orders.shipment` | `Shipment` |
| `access_code_` | `orders.reservations[].accessCodes[]` | `AccessCode` |
| `incident_` | `incidents` | `Incident` |
| `cell_opening_` | `orders.reservations[].accessCodes[].openings[]` or `incidents.serviceOpenings[]` | `CellOpening` |
| `payment_` | `orders.payments[]` | `Payment` |
| `audit_event_` | `auditEvents` | `AuditEvent` |

An order carries at most two reservation legs and up to four access codes in the benchmark data. Each leg holds its codes, and each code holds its openings. An order also carries its charges and refunds. A shipment is an optional subdocument in MongoDB and a second label on an `Order` node in Neo4j. MongoDB puts SERVICE openings in the referenced incident; it puts APP and KEYPAD openings under their access code. Neo4j uses one `CellOpening` node per journal record and relates it to exactly one grant.

## Types and canonical values

| Logical value | PostgreSQL | MySQL | MongoDB | Neo4j |
|---|---|---|---|---|
| Logical ids and references | `bigint` | `BIGINT`, supplied by the generator | BSON Int64 | `INTEGER` or an edge endpoint's id |
| Cell number and weekday | `smallint` | `SMALLINT` | BSON Int32 | `INTEGER` |
| Text and enum values | `text` or `varchar(n)` | `TEXT` or `VARCHAR(n)`, `utf8mb4_0900_bin` | BSON string | `STRING` |
| Actor and Keycloak ids stored as UUID columns | `uuid` | `CHAR(36)` | Lowercase UUID string | Lowercase UUID string |
| Timestamps | `timestamptz` | `DATETIME(3)` in UTC | BSON Date | UTC zoned `DATETIME` |
| Opening hours | `time` | `TIME(6)` | `HH:mm:ss.ffffff` string | `HH:mm:ss.ffffff` string |
| Money | `numeric(8,2)` or `numeric(10,2)` in PLN | `DECIMAL` at the same precision and scale | BSON Int64 in grosze | `INTEGER` in grosze |
| Locker coordinates | `geometry(point,4326)` | `POINT SRID 4326` | GeoJSON Point `[longitude, latitude]` | WGS-84 `point` with longitude and latitude |
| Access-code digest | `bytea` with 32 bytes | `BINARY(32)` | BSON binary with 32 bytes | Lowercase hexadecimal string |
| Audit actor and changes | `jsonb` | `JSON` | Object and array of objects | JSON strings |

Timestamp values have millisecond precision in every engine. The opening-hours string preserves PostgreSQL's `24:00:00` closing value. A missing nullable SQL value can be omitted from a document or node and is read back as SQL null. This does not change JSON nulls inside audit objects or arrays. Reconstruction compares parsed JSON, money in grosze and WGS-84 coordinates separately from a distance result.

Neo4j stores both audit fields as JSON strings because a property cannot contain a nested map or an array of maps. Those events contribute to the logical table counts and hashes. Neo4j skips J1–J6 and has no JX1 or JX2.

## Column mapping

A path in the table below gives either a stored value or its reconstruction rule. `required` also covers canonical `NOT NULL` columns and primary keys.

| PostgreSQL column | MySQL column | MongoDB path or rule | Neo4j property or rule | SQL nullability |
|---|---|---|---|---|
| `lockermat_.id_` | `lockermat_.id_` | `lockermats._id` | `Lockermat.id` | required |
| `lockermat_.code_` | `lockermat_.code_` | `lockermats.code` | `Lockermat.code` | required |
| `lockermat_.name_` | `lockermat_.name_` | `lockermats.name` | `Lockermat.name` | required |
| `lockermat_.address_` | `lockermat_.address_` | `lockermats.address` | `Lockermat.address` | required |
| `lockermat_.location_` | `lockermat_.location_` | `lockermats.location` | `Lockermat.location` | required |
| `lockermat_.time_zone_` | `lockermat_.time_zone_` | `lockermats.timeZone` | `Lockermat.timeZone` | required |
| `lockermat_.status_` | `lockermat_.status_` | `lockermats.status` | `Lockermat.status` | required |
| `lockermat_.created_at_` | `lockermat_.created_at_` | `lockermats.createdAt` | `Lockermat.createdAt` | required |
| `lockermat_opening_hours_.id_` | `lockermat_opening_hours_.id_` | `lockermats.openingHours[].id` | `OpeningHours.id` | required |
| `lockermat_opening_hours_.lockermat_id_` | `lockermat_opening_hours_.lockermat_id_` | Parent `lockermats._id` | Incoming `HAS_HOURS` → `Lockermat.id` | required |
| `lockermat_opening_hours_.weekday_` | `lockermat_opening_hours_.weekday_` | `lockermats.openingHours[].weekday` | `OpeningHours.weekday` | required |
| `lockermat_opening_hours_.opens_at_` | `lockermat_opening_hours_.opens_at_` | `lockermats.openingHours[].opensAt` | `OpeningHours.opensAt` | required |
| `lockermat_opening_hours_.closes_at_` | `lockermat_opening_hours_.closes_at_` | `lockermats.openingHours[].closesAt` | `OpeningHours.closesAt` | required |
| `lockermat_cell_.id_` | `lockermat_cell_.id_` | `lockermats.cells[].id` | `Cell.id` | required |
| `lockermat_cell_.lockermat_id_` | `lockermat_cell_.lockermat_id_` | Parent `lockermats._id` | Incoming `HAS_CELL` → `Lockermat.id` | required |
| `lockermat_cell_.number_` | `lockermat_cell_.number_` | `lockermats.cells[].number` | `Cell.number` | required |
| `lockermat_cell_.size_` | `lockermat_cell_.size_` | `lockermats.cells[].size` | `Cell.size` | required |
| `lockermat_cell_.status_` | `lockermat_cell_.status_` | `lockermats.cells[].status` | `Cell.status` | required |
| `tariff_.id_` | `tariff_.id_` | `tariffs._id` | `Tariff.id` | required |
| `tariff_.size_` | `tariff_.size_` | `tariffs.size` | `Tariff.size` | required |
| `tariff_.valid_from_` | `tariff_.valid_from_` | `tariffs.validFrom` | `Tariff.validFrom` | required |
| `tariff_.valid_to_` | `tariff_.valid_to_` | `tariffs.validTo` | `Tariff.validTo` | nullable |
| `tariff_.storage_price_per_day_` | `tariff_.storage_price_per_day_` | `tariffs.storagePricePerDay` | `Tariff.storagePricePerDay` | required |
| `tariff_.shipment_price_` | `tariff_.shipment_price_` | `tariffs.shipmentPrice` | `Tariff.shipmentPrice` | required |
| `tariff_.overstay_price_per_day_` | `tariff_.overstay_price_per_day_` | `tariffs.overstayPricePerDay` | `Tariff.overstayPricePerDay` | required |
| `customer_.id_` | `customer_.id_` | `customers._id` | `Customer.id` | required |
| `customer_.keycloak_id_` | `customer_.keycloak_id_` | `customers.keycloakId` | `Customer.keycloakId` | required |
| `customer_.phone_` | `customer_.phone_` | `customers.phone` | `Customer.phone` | nullable |
| `customer_.company_name_` | `customer_.company_name_` | `customers.companyName` | `Customer.companyName` | nullable |
| `customer_.tax_id_` | `customer_.tax_id_` | `customers.taxId` | `Customer.taxId` | nullable |
| `customer_.billing_address_` | `customer_.billing_address_` | `customers.billingAddress` | `Customer.billingAddress` | nullable |
| `customer_.terms_version_` | `customer_.terms_version_` | `customers.termsVersion` | `Customer.termsVersion` | required |
| `customer_.terms_accepted_at_` | `customer_.terms_accepted_at_` | `customers.termsAcceptedAt` | `Customer.termsAcceptedAt` | required |
| `customer_.created_at_` | `customer_.created_at_` | `customers.createdAt` | `Customer.createdAt` | required |
| `order_.id_` | `order_.id_` | `orders._id` | `Order.id` | required |
| `order_.number_` | `order_.number_` | `orders.number` | `Order.number` | required |
| `order_.customer_id_` | `order_.customer_id_` | `orders.customerId` | `Order.customerId`, copied from `PLACED` | required |
| `order_.type_` | `order_.type_` | `orders.type` | `Order.type` | required |
| `order_.size_` | `order_.size_` | `orders.size` | `Order.size` | required |
| `order_.tariff_id_` | `order_.tariff_id_` | `orders.tariffId` | `Order.tariffId`, copied from `PRICED_BY` | required |
| `order_.status_` | `order_.status_` | `orders.status` | `Order.status` | required |
| `order_.price_` | `order_.price_` | `orders.price` | `Order.price` | required |
| `order_.payment_deadline_` | `order_.payment_deadline_` | `orders.paymentDeadline` | `Order.paymentDeadline` | required |
| `order_.created_at_` | `order_.created_at_` | `orders.createdAt` | `Order.createdAt` | required |
| `order_.closed_at_` | `order_.closed_at_` | `orders.closedAt` | `Order.closedAt` | nullable |
| `reservation_.id_` | `reservation_.id_` | `orders.reservations[].id` | `Reservation.id` | required |
| `reservation_.order_id_` | `reservation_.order_id_` | Parent `orders._id` | Incoming `HAS_LEG` → `Order.id` | required |
| `reservation_.order_type_` | `reservation_.order_type_` | From `leg` (STORAGE or SHIPMENT) | From `Reservation.leg` (STORAGE or SHIPMENT) | required |
| `reservation_.size_` | `reservation_.size_` | `orders.reservations[].size` | `Reservation.size` | required |
| `reservation_.cell_id_` | `reservation_.cell_id_` | `orders.reservations[].cellId` | Outgoing `IN_CELL` → `Cell.id` | required |
| `reservation_.leg_` | `reservation_.leg_` | `orders.reservations[].leg` | `Reservation.leg` | required |
| `reservation_.from_` | `reservation_.from_` | `orders.reservations[].from` | `Reservation.from` | required |
| `reservation_.to_` | `reservation_.to_` | `orders.reservations[].to` | `Reservation.to` | required |
| `reservation_.status_` | `reservation_.status_` | `orders.reservations[].status` | `Reservation.status` | required |
| `reservation_.deposited_at_` | `reservation_.deposited_at_` | `orders.reservations[].depositedAt` | `Reservation.depositedAt` | nullable |
| `reservation_.collected_at_` | `reservation_.collected_at_` | `orders.reservations[].collectedAt` | `Reservation.collectedAt` | nullable |
| `shipment_.id_` | `shipment_.id_` | `orders.shipment.id` | `Shipment.shipmentId` | required |
| `shipment_.order_id_` | `shipment_.order_id_` | Parent `orders._id` | `Shipment.id` (same as Order id) | required |
| `shipment_.order_type_` | `shipment_.order_type_` | Literal `SHIPMENT` | Literal `SHIPMENT` | required |
| `shipment_.recipient_name_` | `shipment_.recipient_name_` | `orders.shipment.recipientName` | `Shipment.recipientName` | required |
| `shipment_.recipient_phone_` | `shipment_.recipient_phone_` | `orders.shipment.recipientPhone` | `Shipment.recipientPhone` | required |
| `shipment_.declared_value_` | `shipment_.declared_value_` | `orders.shipment.declaredValue` | `Shipment.declaredValue` | required |
| `shipment_.courier_keycloak_id_` | `shipment_.courier_keycloak_id_` | `orders.shipment.courierKeycloakId` | `Shipment.courierKeycloakId` | nullable |
| `shipment_.courier_assigned_at_` | `shipment_.courier_assigned_at_` | `orders.shipment.courierAssignedAt` | `Shipment.courierAssignedAt` | nullable |
| `access_code_.id_` | `access_code_.id_` | `orders.reservations[].accessCodes[].id` | `AccessCode.id` | required |
| `access_code_.reservation_id_` | `access_code_.reservation_id_` | Parent `orders.reservations[].id` | Incoming `HAS_CODE` → `Reservation.id` | required |
| `access_code_.purpose_` | `access_code_.purpose_` | `orders.reservations[].accessCodes[].purpose` | `AccessCode.purpose` | required |
| `access_code_.code_hmac_` | `access_code_.code_hmac_` | `orders.reservations[].accessCodes[].codeHmac` | `AccessCode.codeHmac` | required |
| `access_code_.sent_to_phone_` | `access_code_.sent_to_phone_` | `orders.reservations[].accessCodes[].sentToPhone` | `AccessCode.sentToPhone` | nullable |
| `access_code_.valid_from_` | `access_code_.valid_from_` | `orders.reservations[].accessCodes[].validFrom` | `AccessCode.validFrom` | required |
| `access_code_.valid_to_` | `access_code_.valid_to_` | `orders.reservations[].accessCodes[].validTo` | `AccessCode.validTo` | required |
| `access_code_.status_` | `access_code_.status_` | `orders.reservations[].accessCodes[].status` | `AccessCode.status` | required |
| `access_code_.created_at_` | `access_code_.created_at_` | `orders.reservations[].accessCodes[].createdAt` | `AccessCode.createdAt` | required |
| `access_code_.used_at_` | `access_code_.used_at_` | `orders.reservations[].accessCodes[].usedAt` | `AccessCode.usedAt` | nullable |
| `incident_.id_` | `incident_.id_` | `incidents._id` | `Incident.id` | required |
| `incident_.cell_id_` | `incident_.cell_id_` | `incidents.cellId` | `Incident.cellId`, copied from `AT_CELL` | required |
| `incident_.reservation_id_` | `incident_.reservation_id_` | `incidents.reservationId` | Optional `ABOUT` → `Reservation.id` | nullable |
| `incident_.order_id_` | `incident_.order_id_` | `incidents.orderId` | `Incident.orderId`, copied through `ABOUT` and `HAS_LEG` | nullable |
| `incident_.source_` | `incident_.source_` | `incidents.source` | `Incident.source` | required |
| `incident_.reported_by_keycloak_id_` | `incident_.reported_by_keycloak_id_` | `incidents.reportedByKeycloakId` | `Incident.reportedByKeycloakId` | nullable |
| `incident_.type_` | `incident_.type_` | `incidents.type` | `Incident.type` | required |
| `incident_.description_` | `incident_.description_` | `incidents.description` | `Incident.description` | required |
| `incident_.status_` | `incident_.status_` | `incidents.status` | `Incident.status` | required |
| `incident_.resolution_` | `incident_.resolution_` | `incidents.resolution` | `Incident.resolution` | nullable |
| `incident_.resolved_by_keycloak_id_` | `incident_.resolved_by_keycloak_id_` | `incidents.resolvedByKeycloakId` | `Incident.resolvedByKeycloakId` | nullable |
| `incident_.created_at_` | `incident_.created_at_` | `incidents.createdAt` | `Incident.createdAt` | required |
| `incident_.resolved_at_` | `incident_.resolved_at_` | `incidents.resolvedAt` | `Incident.resolvedAt` | nullable |
| `cell_opening_.id_` | `cell_opening_.id_` | `orders.reservations[].accessCodes[].openings[].id` or `incidents.serviceOpenings[].id` | `CellOpening.id` | required |
| `cell_opening_.access_code_id_` | `cell_opening_.access_code_id_` | Parent `orders.reservations[].accessCodes[].id` for a code opening, otherwise null | Optional `OPENED_WITH` → `AccessCode.id` | nullable |
| `cell_opening_.incident_id_` | `cell_opening_.incident_id_` | Parent `incidents._id` for a service opening, otherwise null | `CellOpening.incidentId`, copied from optional `OPENED_FOR` | nullable |
| `cell_opening_.channel_` | `cell_opening_.channel_` | `orders.reservations[].accessCodes[].openings[].channel` or `incidents.serviceOpenings[].channel` | `CellOpening.channel` | required |
| `cell_opening_.actor_keycloak_id_` | `cell_opening_.actor_keycloak_id_` | `orders.reservations[].accessCodes[].openings[].actorKeycloakId` or `incidents.serviceOpenings[].actorKeycloakId` | `CellOpening.actorKeycloakId` | nullable |
| `cell_opening_.result_` | `cell_opening_.result_` | `orders.reservations[].accessCodes[].openings[].result` or `incidents.serviceOpenings[].result` | `CellOpening.result` | required |
| `cell_opening_.requested_at_` | `cell_opening_.requested_at_` | `orders.reservations[].accessCodes[].openings[].requestedAt` or `incidents.serviceOpenings[].requestedAt` | `CellOpening.requestedAt` | required |
| `cell_opening_.closed_at_` | `cell_opening_.closed_at_` | `orders.reservations[].accessCodes[].openings[].closedAt` or `incidents.serviceOpenings[].closedAt` | `CellOpening.closedAt` | nullable |
| `payment_.id_` | `payment_.id_` | `orders.payments[].id` | `Payment.id` | required |
| `payment_.order_id_` | `payment_.order_id_` | Parent `orders._id` | Incoming `HAS_PAYMENT` → `Order.id` | required |
| `payment_.kind_` | `payment_.kind_` | `orders.payments[].kind` | `Payment.kind` | required |
| `payment_.amount_` | `payment_.amount_` | `orders.payments[].amount` | `Payment.amount` | required |
| `payment_.status_` | `payment_.status_` | `orders.payments[].status` | `Payment.status` | required |
| `payment_.provider_` | `payment_.provider_` | `orders.payments[].provider` | `Payment.provider` | required |
| `payment_.provider_ref_` | `payment_.provider_ref_` | `orders.payments[].providerRef` | `Payment.providerRef` | nullable |
| `payment_.refund_of_id_` | `payment_.refund_of_id_` | `orders.payments[].refundOfId` | `Payment.refundOfId`, copied from optional `REFUND_OF` | nullable |
| `payment_.incident_id_` | `payment_.incident_id_` | `orders.payments[].incidentId` | `Payment.incidentId`, copied from optional `COMPENSATES` | nullable |
| `payment_.refundable_id_` | `payment_.refundable_id_` | From `id`, `kind` and `status` | From `Payment.id`, `kind` and `status` | nullable |
| `payment_.created_at_` | `payment_.created_at_` | `orders.payments[].createdAt` | `Payment.createdAt` | required |
| `payment_.completed_at_` | `payment_.completed_at_` | `orders.payments[].completedAt` | `Payment.completedAt` | nullable |
| `audit_event_.id_` | `audit_event_.id_` | `auditEvents._id` | `AuditEvent.id` | required |
| `audit_event_.at_` | `audit_event_.at_` | `auditEvents.at` | `AuditEvent.at` | required |
| `audit_event_.entity_` | `audit_event_.entity_` | `auditEvents.entity` | `AuditEvent.entity` | required |
| `audit_event_.entity_id_` | `audit_event_.entity_id_` | `auditEvents.entityId` | `AuditEvent.entityId` | required |
| `audit_event_.action_` | `audit_event_.action_` | `auditEvents.action` | `AuditEvent.action` | required |
| `audit_event_.actor_` | `audit_event_.actor_` | `auditEvents.actor` | `AuditEvent.actor` (JSON string) | required |
| `audit_event_.changes_` | `audit_event_.changes_` | `auditEvents.changes` | `AuditEvent.changes` (JSON string) | nullable |

## Graph relationships

| Relational source | Relationship type or label | Direction and meaning |
|---|---|---|
| `lockermat_opening_hours_` | `HAS_HOURS` | Lockermat → OpeningHours |
| `lockermat_cell_` | `HAS_CELL` | Lockermat → Cell |
| `order_` | `PLACED` | Customer → Order |
| `order_` | `PRICED_BY` | Order → Tariff |
| `reservation_` | `HAS_LEG` | Order → Reservation |
| `reservation_` | `IN_CELL` | Reservation → Cell |
| `shipment_` | `Shipment` | Same node as the Order; order type is SHIPMENT |
| `access_code_` | `HAS_CODE` | Reservation → AccessCode |
| `incident_` | `AT_CELL` | Incident → Cell |
| `incident_` | `ABOUT` | Incident → Reservation; verify the order and cell through that reservation |
| `cell_opening_` | `OPENED_WITH` | CellOpening → AccessCode |
| `cell_opening_` | `OPENED_FOR` | CellOpening → Incident |
| `payment_` | `HAS_PAYMENT` | Order → Payment |
| `payment_` | `REFUND_OF` | Payment → captured Payment; validate order and provider |
| `payment_` | `COMPENSATES` | Payment → Incident; validate order |
| `shipment_` | `SHIPS_TO` | Origin `Lockermat` → destination `Lockermat` with `orderId` and `at` |

Each foreign key recovered by traversal uses the logical id of the relevant node, not Neo4j's element id. Relationship structure models the reference. The loader and write adapters preserve the intended cardinality and check composite references against the linked rows. The PostgreSQL build validates all canonical keys before import.

## Derived data

| Object | Source and maintenance |
|---|---|
| MongoDB `orders.reservations[].lockermatId` | Resolve the reservation's cell through the canonical cell-to-locker relationship during import and on any newly inserted or relocated reservation. |
| MongoDB `orders.shipment.originLockermatId`, `destinationLockermatId` | Resolve the two legs through their cells. Update in the shipment transaction, along with the two legs and the derived link. |
| MongoDB `shipLinks` | One document per shipment. Use the order id as BSON `_id` and as `orderId`, take `at` from order creation, and take `from` and `to` from the origin and destination lockers. C4 inserts it in the order transaction. D2 and D5 remove it in the transaction that deletes the order and its incidents. R8 follows `from` and filters by `at`. |
| Neo4j `SHIPS_TO` | The same origin, destination, order id and order timestamp, stored as one relationship per shipment. C4 creates the relationship and D2 and D5 delete it via its `orderId` index. |
| Neo4j indexed reference properties | `Order.customerId`, `Order.tariffId`, `Incident.cellId`, `Incident.orderId`, `CellOpening.incidentId`, `Payment.incidentId` and `Payment.refundOfId` agree with the edges in the column map. Write each copied value and its edge in the same transaction. |
| MongoDB `cells[].guardSeq`, Neo4j `Cell._guard` | Increment the guard inside the transaction before checking or entering a live booking or actual occupancy. Verification ignores this property. |
| Derived SQL columns | `reservation_.order_type_` follows its leg, and `shipment_.order_type_` is always SHIPMENT. `payment_.refundable_id_` is the payment id for a COMPLETED CHARGE, EXTENSION or OVERSTAY and null otherwise. MongoDB and Neo4j reconstruct these values using the source fields. |
| MySQL `excl_guard_` | Two stable lock rows, one for tariff intervals and one for overlapping HMAC windows. Each row is keyed by its exclusion name. This translation table and the derived shipment links are excluded from canonical table totals and hashes. |

## Constraint enforcement

[Index and constraint map](indexes.yaml) identifies each PostgreSQL constraint and index by table and catalog name. A BASE entry gives concrete objects in each engine or the reason that the engine does not need a separate object. The schema's column-level `NOT NULL` rules appear in the column map. Names, scope and ordered keys distinguish physical indexes. Objects with `predicate` represent PostgreSQL partial indexes, MySQL CASE expressions or MongoDB `partialFilterExpression` indexes. An index's comparison scope is its table, collection, node label or relationship type.

| Rule | PostgreSQL | MySQL 8.4 | MongoDB 8 | Neo4j Community |
|---|---|---|---|---|
| Primary identity | PK and sequence | PK; loader assigns ids | Unique root `_id`; embedded ids validated by PostgreSQL and indexed where writes address a specific element | Unique `id` per node label. `:Shipment(shipmentId)` preserves the shipment row's distinct canonical id. |
| Required fields, scalar types and enum values | Native types, `NOT NULL`, CHECK | Native types, `NOT NULL`, CHECK | `$jsonSchema` required fields, types and enums | PostgreSQL validates before import. Community provides property uniqueness, with property existence and type rules validated by the adapters. |
| Foreign and composite keys | FK with restricted parent deletes | FK with restricted parent deletes and explicitly unique referenced keys | Embedded parent or scalar reference. PostgreSQL validates the dataset, and D2, D5 and D6 keep references consistent inside a transaction. | Edges and labels encode the references. PostgreSQL validates composite keys, and write transactions preserve endpoints and cardinality. |
| Globally unique business keys | UNIQUE | UNIQUE | Unique indexes on locker code, customer Keycloak id and order number | Uniqueness constraints on the equivalent properties |
| Remaining UNIQUE rules | UNIQUE or partial unique | UNIQUE or conditional functional unique CASE key | Data validated by PostgreSQL. A unique multikey index cannot enforce uniqueness within one document's array. A single subdocument represents each shipment. | Same-node representation limits a shipment to one row per order. Other pair keys and conditional uniqueness are validated by PostgreSQL. |
| Domain and cross-field CHECKs | CHECK | CHECK with equivalent expressions, including JSON type tests | PostgreSQL validates cross-field rules. Validator checks the actor object with required `kind` and that changes is an array when present. | PostgreSQL validates the rules; no native CHECK. |
| Tariff intervals | `tariff_no_overlap__ex` | Lock the tariff row in `excl_guard_`, then probe the size and interval. | PostgreSQL validates intervals before import. | PostgreSQL validates intervals before import. |
| Live reservation overlap | `reservation_no_double_booking__ex` | Lock the cell row, then probe BOOKED and OCCUPIED intervals. | Increment `guardSeq`, then query the live intervals in the transaction. | Lock the `Cell` via `_guard`, then traverse its live intervals in the transaction. |
| Actual occupancy overlap | `reservation_actual_occupancy__ex` | Lock the cell row, then probe deposited reservations with an open upper bound when applicable. | The same cell guard precedes the actual-occupancy check. | The same cell lock precedes the actual-occupancy check. |
| HMAC validity windows | `access_code_hmac_window__ex` | Lock the HMAC row in `excl_guard_`, then probe overlapping windows. | PostgreSQL validates the dataset; benchmark inserts use the digest derived from each new code id. | PostgreSQL validates the dataset; benchmark inserts use the digest derived from each new code id. |
| Active purposes per reservation | `access_code_active_purpose__ex` | Lock the reservation row, then probe active codes of the same purpose. | PostgreSQL validates the dataset; benchmark orders issue distinct purposes on fresh legs and redemption retires active codes. | PostgreSQL validates the dataset; benchmark orders issue distinct purposes on fresh legs and redemption retires active codes. |

MySQL exclusion triggers use locking reads, half-open intervals, and the same predicates as PostgreSQL. On UPDATE they exclude the row being updated and return immediately when the change cannot introduce an overlap. A null upper endpoint denotes an unbounded interval. A conflicting row signals `45000` with `excl:<constraint name without __ex>`. In MySQL, the coordinate check uses `ST_Longitude` and `ST_Latitude`. Point conversion specifies `axis-order=long-lat`. Opening-hour checks account for MySQL `TIME`'s wider domain.

## Index configurations

- BASE contains the schema's declared indexes and constraints plus two PostgreSQL FK-support indexes. MySQL's final automatic FK indexes are the named constraints whose ordered child columns are not the leading prefix of a declared, unconditional B-tree index. MongoDB's embedded id indexes provide a lookup path, with the SQL uniqueness of the logical row id still validated by PostgreSQL. Neo4j's endpoint traversals provide the equivalent lookup where no property index is listed.
- IDX keeps BASE and adds IX1–IX4 in all four engines, plus JX1 and JX2 in PostgreSQL, MySQL and MongoDB. The map records the BA reads served and the writes that maintain each added index. J5 and U3 also run in both configurations because an IDX index can accelerate target discovery. The H1 write comparison uses C2, C3, C4, C6, U1, U5 and J1, with J1 limited to the engines that support it.
- C2 appends code openings so that each engine adds an IX4 entry. MongoDB filters IX3 and IX4 with `$elemMatch` to use both range bounds on the same embedded element. When translating to MongoDB, it omits the courier field when unassigned so that its BASE `$exists` predicate matches the SQL non-null predicate. For JX2, PostgreSQL disables GIN fast update. MySQL repeats the functional expressions in its reads and confirms treatment of JSON null and overlength values in the DDL acceptance.
- The map is stored in JSON-compatible YAML so `tools/check-models` can validate it with the Python standard library. Run the checker from the repository root. Physical catalog verification follows after the engine DDL exists.
