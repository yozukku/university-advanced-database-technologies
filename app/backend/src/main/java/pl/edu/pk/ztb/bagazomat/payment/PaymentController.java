package pl.edu.pk.ztb.bagazomat.payment;

import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/** @author Anton Gorokh */
@RestController
class PaymentController {

	private final PaymentService paymentService;

	PaymentController(PaymentService paymentService) {
		this.paymentService = paymentService;
	}

	@PostMapping("/api/orders/{id}/payments")
	@ResponseStatus(HttpStatus.CREATED)
	public PaymentView pay(@AuthenticationPrincipal Jwt jwt, @PathVariable long id, @RequestBody MockPayment request) {
		return paymentService.pay(jwt, id, request);
	}
}
