package pl.edu.pk.ztb.bagazomat.demo;

import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.NativeQuery;
import org.springframework.data.repository.Repository;
import pl.edu.pk.ztb.bagazomat.lockermat.CellSize;
import pl.edu.pk.ztb.bagazomat.shipment.Shipment;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;

/** @author Anton Gorokh */
public interface ShipmentSimulationRepository extends Repository<Shipment, Long> {

	@NativeQuery("select now()")
	Instant now();

	@NativeQuery("select nextval('reservation_id_seq_')")
	long nextReservationId();

	@NativeQuery("""
			select c.id_ as "cellId", c.lockermat_id_ as "lockermatId", c.size_ as size
			from lockermat_cell_ c
			         join lockermat_ l on l.id_ = c.lockermat_id_
			where l.status_ = 'ACTIVE' and c.status_ = 'IN_SERVICE'
			  and not exists (select 1 from reservation_ r
			                  where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
			                    and tstzrange(r.from_, r.to_, '[)') && tstzrange(cast(:from as timestamptz), cast(:to as timestamptz), '[)'))
			  and not exists (select 1 from reservation_ r
			                  where r.cell_id_ = c.id_ and r.deposited_at_ is not null
			                    and tstzrange(r.deposited_at_, r.collected_at_, '[)') && tstzrange(cast(:from as timestamptz), null, '[)'))
			order by random()
			limit 1
			for update of c skip locked
			""")
	Optional<FreeCell> findDestinationCell(Instant from, Instant to);

	@NativeQuery("""
			select c.id_
			from lockermat_cell_ c
			         join lockermat_ l on l.id_ = c.lockermat_id_
			where l.status_ = 'ACTIVE' and l.id_ <> :destinationLockermatId
			  and c.size_ = :size and c.status_ = 'IN_SERVICE'
			  and not exists (select 1 from reservation_ r
			                  where r.cell_id_ = c.id_ and r.deposited_at_ is not null
			                    and tstzrange(r.deposited_at_, r.collected_at_, '[)')
			                        && tstzrange(cast(:depositedAt as timestamptz), cast(:collectedAt as timestamptz), '[)'))
			order by c.lockermat_id_, c.number_
			limit 1
			for update of c skip locked
			""")
	Optional<Long> findOriginCell(long destinationLockermatId, String size, Instant depositedAt, Instant collectedAt);

	@Modifying
	@NativeQuery("""
			insert into order_ (id_, number_, customer_id_, type_, size_, tariff_id_, status_, price_, payment_deadline_)
			select :id, :number, u.id_, 'SHIPMENT', t.size_, t.id_, 'PAID', t.shipment_price_, now() + interval '15 minutes'
			from tariff_ t
			         join customer_ u on u.keycloak_id_ = :sender
			where t.size_ = :size
			  and tstzrange(t.valid_from_, t.valid_to_, '[)') @> now()
			""")
	int insertPaidOrder(long id, String number, UUID sender, String size);

	@Modifying
	@NativeQuery("""
			insert into reservation_ (id_, order_id_, size_, cell_id_, leg_, from_, to_, status_, deposited_at_, collected_at_)
			select :id, o.id_, o.size_, :cellId, 'ORIGIN', cast(:depositedAt as timestamptz), cast(:collectedAt as timestamptz),
			       'COMPLETED', cast(:depositedAt as timestamptz), cast(:collectedAt as timestamptz)
			from order_ o
			where o.id_ = :orderId
			""")
	void insertCollectedOrigin(long id, long orderId, long cellId, Instant depositedAt, Instant collectedAt);

	@Modifying
	@NativeQuery("""
			insert into reservation_ (id_, order_id_, size_, cell_id_, leg_, from_, to_, status_, deposited_at_)
			select :id, o.id_, o.size_, :cellId, 'DESTINATION', cast(:from as timestamptz), cast(:to as timestamptz),
			       'OCCUPIED', cast(:from as timestamptz)
			from order_ o
			where o.id_ = :orderId
			""")
	void insertOccupiedDestination(long id, long orderId, long cellId, Instant from, Instant to);

	interface FreeCell {

		Long getCellId();

		Long getLockermatId();

		CellSize getSize();
	}
}
