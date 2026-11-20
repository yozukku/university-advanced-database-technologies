package pl.edu.pk.ztb.bagazomat.order;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.NativeQuery;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/** @author Anton Gorokh */
public interface OrderRepository extends JpaRepository<Order, Long> {

	String STORAGE_ORDERS = """
			select o.id_ as id, o.number_ as number, o.status_ as status, o.size_ as size, o.price_ as price,
			       o.payment_deadline_ as "paymentDeadline", o.created_at_ as "createdAt",
			       r.id_ as "reservationId", r.status_ as "reservationStatus", r.from_ as "from", r.to_ as "to",
			       l.name_ as "lockermatName", l.address_ as "lockermatAddress", c.number_ as "cellNumber"
			from order_ o
			         join customer_ u on u.id_ = o.customer_id_
			         join reservation_ r on r.order_id_ = o.id_
			         join lockermat_cell_ c on c.id_ = r.cell_id_
			         join lockermat_ l on l.id_ = c.lockermat_id_
			where u.keycloak_id_ = :subject and o.type_ = 'STORAGE'
			""";

	@NativeQuery("select nextval('order_id_seq_')")
	long nextId();

	@Modifying
	@NativeQuery("""
			insert into order_ (id_, number_, customer_id_, type_, size_, tariff_id_, price_, payment_deadline_)
			select :id, :number, u.id_, 'STORAGE', t.size_, t.id_,
			       t.storage_price_per_day_ * ceil(extract(epoch from (cast(:to as timestamptz) - cast(:from as timestamptz))) / 86400),
			       least(now() + interval '15 minutes', cast(:to as timestamptz))
			from tariff_ t
			         join customer_ u on u.keycloak_id_ = :subject
			where t.size_ = :size
			  and tstzrange(t.valid_from_, t.valid_to_, '[)') @> now()
			  and cast(:to as timestamptz) > now()
			""")
	int insertStorageOrder(long id, String number, UUID subject, String size, Instant from, Instant to);

	@NativeQuery(STORAGE_ORDERS + "order by o.created_at_ desc, o.id_ desc")
	List<OrderView> findStorageOrders(UUID subject);

	@NativeQuery(STORAGE_ORDERS + "and o.id_ = :id")
	Optional<OrderView> findStorageOrder(UUID subject, long id);
}
