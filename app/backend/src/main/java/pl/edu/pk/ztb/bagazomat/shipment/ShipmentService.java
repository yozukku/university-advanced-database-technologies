package pl.edu.pk.ztb.bagazomat.shipment;

import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;
import pl.edu.pk.ztb.bagazomat.api.NotFoundException;

import java.util.List;
import java.util.UUID;

/** @author Anton Gorokh */
@Service
public class ShipmentService {

	private final ShipmentRepository shipmentRepository;

	public ShipmentService(ShipmentRepository shipmentRepository) {
		this.shipmentRepository = shipmentRepository;
	}

	List<IncomingShipment> findIncoming(Jwt jwt) {
		return shipmentRepository.findIncoming(subjectOf(jwt));
	}

	public IncomingShipment findIncoming(Jwt jwt, long orderId) {
		return shipmentRepository.findIncoming(subjectOf(jwt), orderId)
				.orElseThrow(NotFoundException::new);
	}

	private UUID subjectOf(Jwt jwt) {
		return UUID.fromString(jwt.getSubject());
	}
}
