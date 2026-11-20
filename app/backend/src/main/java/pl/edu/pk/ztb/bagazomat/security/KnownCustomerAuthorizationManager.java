package pl.edu.pk.ztb.bagazomat.security;

import org.springframework.security.authorization.AuthorizationDecision;
import org.springframework.security.authorization.AuthorizationManager;
import org.springframework.security.authorization.AuthorizationResult;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.security.web.access.intercept.RequestAuthorizationContext;
import org.springframework.stereotype.Component;
import pl.edu.pk.ztb.bagazomat.customer.CustomerRepository;

import java.util.UUID;
import java.util.function.Supplier;

/** @author Anton Gorokh */
@Component
class KnownCustomerAuthorizationManager implements AuthorizationManager<RequestAuthorizationContext> {

	private final CustomerRepository customerRepository;

	KnownCustomerAuthorizationManager(CustomerRepository customerRepository) {
		this.customerRepository = customerRepository;
	}

	@Override
	public AuthorizationResult authorize(Supplier<? extends Authentication> authentication, RequestAuthorizationContext context) {
		return new AuthorizationDecision(isKnownCustomer(authentication.get()));
	}

	private boolean isKnownCustomer(Authentication authentication) {
		return authentication instanceof JwtAuthenticationToken token
				&& customerRepository.existsByKeycloakId(UUID.fromString(token.getName()));
	}
}
