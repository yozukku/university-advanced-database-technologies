package pl.edu.pk.ztb.bagazomat.shipment;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.NativeQuery;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/** @author Anton Gorokh */
public interface ShipmentRepository extends JpaRepository<Shipment, Long> {

	String INCOMING_SHIPMENTS = """
			select o.id_ as "orderId", r.id_ as "reservationId", r.status_ as status,
			       l.name_ as "lockermatName", l.address_ as "lockermatAddress", c.number_ as "cellNumber",
			       r.from_ as "from", r.to_ as "to"
			from shipment_ s
			         join customer_ u on u.phone_ = s.recipient_phone_
			         join order_ o on o.id_ = s.order_id_
			         join reservation_ r on r.order_id_ = o.id_
			         join lockermat_cell_ c on c.id_ = r.cell_id_
			         join lockermat_ l on l.id_ = c.lockermat_id_
			where u.keycloak_id_ = :subject and r.leg_ = 'DESTINATION'
			  and (r.status_ = 'OCCUPIED' or (r.status_ = 'COMPLETED' and r.collected_at_ > now() - interval '24 hours'))
			""";

	@NativeQuery(INCOMING_SHIPMENTS + "order by o.created_at_ desc, o.id_ desc")
	List<IncomingShipment> findIncoming(UUID subject);

	@NativeQuery(INCOMING_SHIPMENTS + "and o.id_ = :orderId")
	Optional<IncomingShipment> findIncoming(UUID subject, long orderId);
}
