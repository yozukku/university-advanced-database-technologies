package pl.edu.pk.ztb.bagazomat.api;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.sql.SQLException;
import java.util.Set;

/** @author Anton Gorokh */
@RestControllerAdvice
class ApiErrorHandler {

	private static final Logger LOG = LoggerFactory.getLogger(ApiErrorHandler.class);

	private static final Set<String> CONFLICT_STATES = Set.of("23P01", "23505");

	private static final ApiError CONFLICT = new ApiError("CONFLICT", "Ktoś właśnie zmienił te dane. Odśwież widok i spróbuj ponownie.");
	private static final ApiError INTERNAL_ERROR = new ApiError("INTERNAL_ERROR", "Wystąpił nieoczekiwany błąd. Spróbuj ponownie później.");

	@ExceptionHandler(DataIntegrityViolationException.class)
	ResponseEntity<ApiError> handleIntegrityViolation(DataIntegrityViolationException exception) {
		if (isConflict(exception)) {
			return ResponseEntity.status(HttpStatus.CONFLICT).body(CONFLICT);
		}
		LOG.error("Nieoczekiwane naruszenie integralności danych", exception);
		return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(INTERNAL_ERROR);
	}

	private boolean isConflict(Throwable exception) {
		for (Throwable cause = exception; cause != null; cause = cause.getCause()) {
			if (cause instanceof SQLException sqlException && CONFLICT_STATES.contains(sqlException.getSQLState())) {
				return true;
			}
		}
		return false;
	}
}
