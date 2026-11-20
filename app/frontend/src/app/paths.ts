export const paths = {
  lockers: '/',
  orders: '/rezerwacje',
  order: (orderId: number) => `/rezerwacje/${orderId}`,
  checkout: (orderId: number) => `/rezerwacje/${orderId}/platnosc`,
  incoming: (reservationId: number) => `/rezerwacje/do-odbioru/${reservationId}`,
}
