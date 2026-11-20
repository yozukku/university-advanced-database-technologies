delimiter //

create trigger tariff_no_overlap__bi
    before insert
    on tariff_
    for each row
begin
    declare locked int;
    declare conflicts int;
    select count(*) into locked from excl_guard_ where rule_ = 'tariff_no_overlap' for update;
    select count(*)
    into conflicts
    from tariff_ force index (tariff_size_from__idx)
    where size_ = new.size_
      and valid_from_ < coalesce(new.valid_to_, timestamp '9999-12-31 00:00:00')
      and coalesce(valid_to_, timestamp '9999-12-31 00:00:00') > new.valid_from_
    for share;
    if conflicts > 0 then
        signal sqlstate '45000' set message_text = 'excl:tariff_no_overlap';
    end if;
end//

create trigger tariff_no_overlap__bu
    before update
    on tariff_
    for each row
begin
    declare locked int;
    declare conflicts int;
    if new.size_ <> old.size_
        or new.valid_from_ < old.valid_from_
        or coalesce(new.valid_to_, timestamp '9999-12-31 00:00:00') > coalesce(old.valid_to_, timestamp '9999-12-31 00:00:00') then
        select count(*) into locked from excl_guard_ where rule_ = 'tariff_no_overlap' for update;
        select count(*)
        into conflicts
        from tariff_ force index (tariff_size_from__idx)
        where size_ = new.size_
          and valid_from_ < coalesce(new.valid_to_, timestamp '9999-12-31 00:00:00')
          and coalesce(valid_to_, timestamp '9999-12-31 00:00:00') > new.valid_from_
          and id_ <> old.id_
        for share;
        if conflicts > 0 then
            signal sqlstate '45000' set message_text = 'excl:tariff_no_overlap';
        end if;
    end if;
end//

create trigger reservation_no_double_booking__bi
    before insert
    on reservation_
    for each row
begin
    declare locked int;
    declare conflicts int;
    if new.status_ in ('BOOKED', 'OCCUPIED') then
        select count(*) into locked from lockermat_cell_ where id_ = new.cell_id_ for update;
        select count(*)
        into conflicts
        from reservation_ force index (reservation_cell_from__idx)
        where cell_id_ = new.cell_id_
          and from_ < new.to_
          and to_ > new.from_
          and status_ in ('BOOKED', 'OCCUPIED')
        for share;
        if conflicts > 0 then
            signal sqlstate '45000' set message_text = 'excl:reservation_no_double_booking';
        end if;
    end if;
end//

create trigger reservation_no_double_booking__bu
    before update
    on reservation_
    for each row
begin
    declare locked int;
    declare conflicts int;
    if new.status_ in ('BOOKED', 'OCCUPIED')
        and (old.status_ not in ('BOOKED', 'OCCUPIED')
            or new.cell_id_ <> old.cell_id_
            or new.from_ < old.from_
            or new.to_ > old.to_) then
        select count(*) into locked from lockermat_cell_ where id_ = new.cell_id_ for update;
        select count(*)
        into conflicts
        from reservation_ force index (reservation_cell_from__idx)
        where cell_id_ = new.cell_id_
          and from_ < new.to_
          and to_ > new.from_
          and status_ in ('BOOKED', 'OCCUPIED')
          and id_ <> old.id_
        for share;
        if conflicts > 0 then
            signal sqlstate '45000' set message_text = 'excl:reservation_no_double_booking';
        end if;
    end if;
end//

create trigger reservation_actual_occupancy__bi
    before insert
    on reservation_
    for each row
begin
    declare locked int;
    declare conflicts int;
    if new.deposited_at_ is not null and (new.collected_at_ is null or new.collected_at_ > new.deposited_at_) then
        select count(*) into locked from lockermat_cell_ where id_ = new.cell_id_ for update;
        select count(*)
        into conflicts
        from reservation_ force index (reservation_cell_from__idx)
        where cell_id_ = new.cell_id_
          and deposited_at_ < coalesce(new.collected_at_, timestamp '9999-12-31 00:00:00')
          and coalesce(collected_at_, timestamp '9999-12-31 00:00:00') > new.deposited_at_
          and (collected_at_ is null or collected_at_ > deposited_at_)
        for share;
        if conflicts > 0 then
            signal sqlstate '45000' set message_text = 'excl:reservation_actual_occupancy';
        end if;
    end if;
end//

create trigger reservation_actual_occupancy__bu
    before update
    on reservation_
    for each row
begin
    declare locked int;
    declare conflicts int;
    if new.deposited_at_ is not null and (new.collected_at_ is null or new.collected_at_ > new.deposited_at_)
        and (old.deposited_at_ is null
            or old.collected_at_ <= old.deposited_at_
            or new.cell_id_ <> old.cell_id_
            or new.deposited_at_ < old.deposited_at_
            or coalesce(new.collected_at_, timestamp '9999-12-31 00:00:00') > coalesce(old.collected_at_, timestamp '9999-12-31 00:00:00')) then
        select count(*) into locked from lockermat_cell_ where id_ = new.cell_id_ for update;
        select count(*)
        into conflicts
        from reservation_ force index (reservation_cell_from__idx)
        where cell_id_ = new.cell_id_
          and deposited_at_ < coalesce(new.collected_at_, timestamp '9999-12-31 00:00:00')
          and coalesce(collected_at_, timestamp '9999-12-31 00:00:00') > new.deposited_at_
          and (collected_at_ is null or collected_at_ > deposited_at_)
          and id_ <> old.id_
        for share;
        if conflicts > 0 then
            signal sqlstate '45000' set message_text = 'excl:reservation_actual_occupancy';
        end if;
    end if;
end//

create trigger access_code_hmac_window__bi
    before insert
    on access_code_
    for each row
begin
    declare locked int;
    declare conflicts int;
    select count(*) into locked from excl_guard_ where rule_ = 'access_code_hmac_window' for update;
    select count(*)
    into conflicts
    from access_code_ force index (access_code_hmac_from__idx)
    where code_hmac_ = new.code_hmac_
      and valid_from_ < new.valid_to_
      and valid_to_ > new.valid_from_
    for share;
    if conflicts > 0 then
        signal sqlstate '45000' set message_text = 'excl:access_code_hmac_window';
    end if;
end//

create trigger access_code_hmac_window__bu
    before update
    on access_code_
    for each row
begin
    declare locked int;
    declare conflicts int;
    if new.code_hmac_ <> old.code_hmac_
        or new.valid_from_ < old.valid_from_
        or new.valid_to_ > old.valid_to_ then
        select count(*) into locked from excl_guard_ where rule_ = 'access_code_hmac_window' for update;
        select count(*)
        into conflicts
        from access_code_ force index (access_code_hmac_from__idx)
        where code_hmac_ = new.code_hmac_
          and valid_from_ < new.valid_to_
          and valid_to_ > new.valid_from_
          and id_ <> old.id_
        for share;
        if conflicts > 0 then
            signal sqlstate '45000' set message_text = 'excl:access_code_hmac_window';
        end if;
    end if;
end//

create trigger access_code_active_purpose__bi
    before insert
    on access_code_
    for each row
begin
    declare locked int;
    declare conflicts int;
    if new.status_ = 'ACTIVE' then
        select count(*) into locked from reservation_ where id_ = new.reservation_id_ for update;
        select count(*)
        into conflicts
        from access_code_ force index (access_code_reservation__idx)
        where reservation_id_ = new.reservation_id_
          and purpose_ = new.purpose_
          and status_ = 'ACTIVE'
          and valid_from_ < new.valid_to_
          and valid_to_ > new.valid_from_
        for share;
        if conflicts > 0 then
            signal sqlstate '45000' set message_text = 'excl:access_code_active_purpose';
        end if;
    end if;
end//

create trigger access_code_active_purpose__bu
    before update
    on access_code_
    for each row
begin
    declare locked int;
    declare conflicts int;
    if new.status_ = 'ACTIVE'
        and (old.status_ <> 'ACTIVE'
            or new.reservation_id_ <> old.reservation_id_
            or new.purpose_ <> old.purpose_
            or new.valid_from_ < old.valid_from_
            or new.valid_to_ > old.valid_to_) then
        select count(*) into locked from reservation_ where id_ = new.reservation_id_ for update;
        select count(*)
        into conflicts
        from access_code_ force index (access_code_reservation__idx)
        where reservation_id_ = new.reservation_id_
          and purpose_ = new.purpose_
          and status_ = 'ACTIVE'
          and valid_from_ < new.valid_to_
          and valid_to_ > new.valid_from_
          and id_ <> old.id_
        for share;
        if conflicts > 0 then
            signal sqlstate '45000' set message_text = 'excl:access_code_active_purpose';
        end if;
    end if;
end//

delimiter ;
