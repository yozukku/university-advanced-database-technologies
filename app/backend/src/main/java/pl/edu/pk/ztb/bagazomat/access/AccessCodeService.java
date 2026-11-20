package pl.edu.pk.ztb.bagazomat.access;

import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import pl.edu.pk.ztb.bagazomat.api.NotFoundException;
import pl.edu.pk.ztb.bagazomat.order.OrderRepository;
import pl.edu.pk.ztb.bagazomat.order.Reservation;
import pl.edu.pk.ztb.bagazomat.order.ReservationRepository;

import java.util.List;
import java.util.UUID;

/** @author Anton Gorokh */
@Service
public class AccessCodeService {

	private final AccessCodeRepository accessCodeRepository;
	private final ReservationRepository reservationRepository;
	private final OrderRepository orderRepository;
	private final AccessCodeHmac accessCodeHmac;

	public AccessCodeService(AccessCodeRepository accessCodeRepository, ReservationRepository reservationRepository, OrderRepository orderRepository,
			AccessCodeHmac accessCodeHmac) {
		this.accessCodeRepository = accessCodeRepository;
		this.reservationRepository = reservationRepository;
		this.orderRepository = orderRepository;
		this.accessCodeHmac = accessCodeHmac;
	}

	@Transactional(propagation = Propagation.MANDATORY)
	public void issueStorageCodes(long orderId) {
		Reservation leg = reservationRepository.findByOrderIdAndStatus(orderId, Reservation.Status.BOOKED)
				.orElseThrow();
		issue(leg, AccessCode.Purpose.DROP_OFF, null);
		issue(leg, AccessCode.Purpose.PICK_UP, null);
	}

	@Transactional(propagation = Propagation.MANDATORY)
	public void issueRecipientPickUpCode(long reservationId, String phone) {
		Reservation leg = reservationRepository.findById(reservationId)
				.orElseThrow();
		issue(leg, AccessCode.Purpose.PICK_UP, phone);
	}

	List<AccessCodeView> findActiveCodes(Jwt jwt, long orderId) {
		if (orderRepository.findStorageOrder(UUID.fromString(jwt.getSubject()), orderId).isEmpty()) {
			throw new NotFoundException();
		}
		return accessCodeRepository.findActiveByOrderId(orderId).stream()
				.map(this::toView)
				.toList();
	}

	private void issue(Reservation leg, AccessCode.Purpose purpose, String sentToPhone) {
		long id = accessCodeRepository.nextId();
		byte[] codeHmac = accessCodeHmac.codeHmacOf(accessCodeHmac.pinOf(id));
		accessCodeRepository.saveAndFlush(new AccessCode(id, leg.getId(), purpose, codeHmac, sentToPhone, leg.getFrom(), leg.getTo()));
	}

	private AccessCodeView toView(AccessCode code) {
		return new AccessCodeView(code.getPurpose(), accessCodeHmac.pinOf(code.getId()), code.getValidFrom(), code.getValidTo());
	}
}
