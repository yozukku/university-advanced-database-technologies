package pl.edu.pk.ztb.bagazomat.order;

import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** @author Anton Gorokh */
@RestController
@RequestMapping("/api/orders")
class OrderController {

	private final OrderService orderService;
	private final OrderCancellationService orderCancellationService;

	OrderController(OrderService orderService, OrderCancellationService orderCancellationService) {
		this.orderService = orderService;
		this.orderCancellationService = orderCancellationService;
	}

	@PostMapping
	@ResponseStatus(HttpStatus.CREATED)
	public OrderView create(@AuthenticationPrincipal Jwt jwt, @RequestBody NewOrder request) {
		return orderService.create(jwt, request);
	}

	@GetMapping
	public List<OrderView> findAll(@AuthenticationPrincipal Jwt jwt) {
		return orderService.findAll(jwt);
	}

	@GetMapping("/{id}")
	public OrderView find(@AuthenticationPrincipal Jwt jwt, @PathVariable long id) {
		return orderService.find(jwt, id);
	}

	@PostMapping("/{id}/cancel")
	public CancelledOrder cancel(@AuthenticationPrincipal Jwt jwt, @PathVariable long id) {
		return orderCancellationService.cancel(jwt, id);
	}
}
