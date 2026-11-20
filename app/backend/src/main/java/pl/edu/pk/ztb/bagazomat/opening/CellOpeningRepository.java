package pl.edu.pk.ztb.bagazomat.opening;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.NativeQuery;
import pl.edu.pk.ztb.bagazomat.order.Reservation;

import java.util.UUID;

/** @author Anton Gorokh */
public interface CellOpeningRepository extends JpaRepository<CellOpening, Long> {

	@NativeQuery("""
			select exists (select 1
			               from cell_opening_ x
			                        join access_code_ a on a.id_ = x.access_code_id_
			                        join reservation_ r on r.id_ = a.reservation_id_
			               where r.order_id_ = :orderId and x.result_ = 'PENDING')
			""")
	boolean hasPendingOpening(long orderId);

	@NativeQuery("select nextval('cell_opening_id_seq_')")
	long nextId();

	@NativeQuery("""
			select r.status_
			from lockermat_cell_ c
			         join reservation_ r on r.cell_id_ = c.id_
			where r.id_ = :reservationId
			for update of c
			""")
	Reservation.Status lockCell(long reservationId);

	@Modifying
	@NativeQuery("""
			insert into cell_opening_ (id_, access_code_id_, channel_, actor_keycloak_id_, result_, requested_at_)
			select :id, a.id_, 'APP', :subject, 'PENDING', statement_timestamp()
			from access_code_ a
			         join reservation_ r on r.id_ = a.reservation_id_
			         join order_ o on o.id_ = r.order_id_
			where r.id_ = :reservationId and o.status_ = 'PAID'
			  and a.status_ = 'ACTIVE'
			  and tstzrange(a.valid_from_, a.valid_to_, '[)') @> statement_timestamp()
			  and ((a.purpose_ = 'DROP_OFF' and r.status_ = 'BOOKED'
			            and not exists (select 1 from reservation_ x
			                            where x.cell_id_ = r.cell_id_ and x.deposited_at_ is not null and x.collected_at_ is null)
			            and not exists (select 1
			                            from cell_opening_ p
			                                     left join access_code_ pa on pa.id_ = p.access_code_id_
			                                     left join reservation_ pr on pr.id_ = pa.reservation_id_
			                                     left join incident_ pi on pi.id_ = p.incident_id_
			                            where p.result_ = 'PENDING' and coalesce(pr.cell_id_, pi.cell_id_) = r.cell_id_))
			    or (a.purpose_ = 'PICK_UP' and r.status_ = 'OCCUPIED'))
			  and a.purpose_ = :purpose
			  and r.leg_ = 'STORAGE'
			  and exists (select 1 from customer_ u
			              where u.id_ = o.customer_id_ and u.keycloak_id_ = :subject)
			""")
	int insertAppOpening(long id, long reservationId, String purpose, UUID subject);

	@Modifying
	@NativeQuery("""
			with opening as (
			         update cell_opening_ set result_ = 'OPENED'
			         where id_ = :id and result_ = 'PENDING'
			         returning access_code_id_, requested_at_),
			     code as (
			         update access_code_ a set status_ = 'USED', used_at_ = o.requested_at_
			         from opening o
			         where a.id_ = o.access_code_id_ and a.status_ = 'ACTIVE'
			         returning a.id_, a.reservation_id_, a.purpose_, o.requested_at_)
			update reservation_ r
			set status_       = case c.purpose_ when 'DROP_OFF' then 'OCCUPIED' else 'COMPLETED' end,
			    deposited_at_ = case c.purpose_ when 'DROP_OFF' then c.requested_at_ else r.deposited_at_ end,
			    collected_at_ = case c.purpose_ when 'PICK_UP' then c.requested_at_ end
			from code c
			where r.id_ = c.reservation_id_
			  and ((c.purpose_ = 'DROP_OFF' and r.status_ = 'BOOKED') or (c.purpose_ = 'PICK_UP' and r.status_ = 'OCCUPIED'))
			""")
	int markOpened(long id);

	@Modifying
	@NativeQuery("update cell_opening_ set result_ = 'DOOR_FAILED' where id_ = :id and result_ = 'PENDING'")
	void markDoorFailed(long id);
}
