create range index ix1__idx for (n:Shipment) on (n.recipientPhone);
create range index ix2__idx for (n:Order) on (n.status, n.createdAt);
create range index ix3__idx for (n:Payment) on (n.createdAt);
create range index ix4__idx for (n:CellOpening) on (n.requestedAt);
call db.resampleOutdatedIndexes();
call db.awaitIndexes(3600);
