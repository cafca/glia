drop table if exists personas;
create table personas (
  id integer primary key autoincrement,
  name string not null,
  email string not null
);