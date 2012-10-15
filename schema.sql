drop table if exists personas;
create table personas (
  id text primary key,
  active int default 0, 
  name text not null,
  email text,
  private text not null,
  public text not null
);

drop table if exists stars;
create table stars (
  id text primary key,
  creator text not null,
  text text not null
);

INSERT INTO personas (id, active, name, email, private, public) 
VALUES ('247a1ca474b04a248c751d0eebf9738f', '1', 'cievent', 'nichte@gmail.com',
'-----BEGIN RSA PRIVATE KEY----- MIIEowIBAAKCAQEAlD1rJejkgo7x8FgL43Plfwtv0ulw9+dpCU0B4WljMpPADqW/ HL4D8n4aS1cnEfXjOq+5F556nwGUeohJTFL0li2SrFfwcB3MaCACO/3corNtfwaS KNyGErHhi56ReVYVWoWcXTkpJnW9kFNR19fM9U2G3U50hc7NQgmJ5HElUHngjTUb EbuhyUMnxS1fR5Hh5l3b1rYiGoNGRzs3/j3jiq1akMKdy8z+rBjH/C8zzjN4Wtzk NDb93NdcgH3iE7HyE0ydNoZ3RDAiTCMwlwibqN0EhzjCWZAEHajcVG9pKfagkxki PCMz6ZdUtjZU+xghYH063DfuZ9MfT3mueBfnVwIDAQABAoIBAQCBU1/iD98jg7/Q 1Y9xnM+v2XNyRpR2wl1hbtxgIggXvMzGOpWTZrac3KTl65+7TJAzx9ArqegCRmeZ ysJfotOdHR8j2gh6V5TXlm08l0nga7bwJfRnT5RsROGnY+w4NgClG4GB1vduhTOe 8QGq06sMqtkow2RmxDdQEHBLauaJ4KXeM5B+qTBJMQlud5cuJzDBiAitM6kNK/YU 8cNXJSbgfvxUpnD5IrEMk573mTPUk7fYfWnOhqEqGDf3qGBM9cc/YlzfxTkUO4jP SA9v7dZ96VcvKBEG9RxkKrq++fnZrUJbQaMuqg2iVbfhFx/hkFeyWPoWWmi8zUYY /+4U2VPRAoGBALnji01jOhQfRO2n1/fZCX6ZhQRGNwtD7CvNtW0jYXz95Lvnj931 xbN8BfTapWYJBNN64Tvg7Z9ZeB2tK1su+eUhyJz7jUv3Lr0QXoGsbjRM13Gv+0li FGLAkfay+gL6cGFa6c2ZDOnhRQkbnTq6o8ys2+T3JL9ky79E9v+W9e+pAoGBAMwm sMfdScg4BZXPp1fw2kkxd9q5d+bXJBNmlD+42i398ZSenCoVh5YN9y7MKTIba6b9 6fF6jDS4un3h5SD5uhiI7q9ICKBHBnfenEMG7lGeMNSCgK7ktnQz16O4EQ9AnnKV NF/w/DhPE9jQyNZMZjrohi/FplXt3RuyD+uhgX7/AoGAZv7EuGQ6UdvhfSx6ZUFE GXlGUk/1P7CqsrqPw6DO60ph6hsrg3ghyoj1Y+2hpx9oJST4lwzRnHEeNJM2apdk rqhBV3mpmGWk5+yh8IdxqFjLJpqzSL2nPfAk7+PK0sugaNDOqrQai5vdfGZof5na GBXO4NZu7f0TRy8XDBbAvcECgYA9pzGcKmgt3z1QkPWoyUQi9p2LoJdlT3PFqCT9 WYYKfbaHe58N1pKr7mvH5kBKsZ1BQU11b90HzwIDIkVgQArDfhcXOFnijZCWgtQO KfmvDGcSxpa2OrwfO8jT2LLOOGWhlQ3MK6sAFmGYCPWeQlRdVfuwUbB6IuuzgYLt VkkVYQKBgGIcJVgQ2P5mrICsAzslFckkK6hsl/F49D5UisdA0/hfXiAtLiLxKdtS VMeBYZb7YNoZvfpV1/b7cVbF5mPmsdxTvopltjN4bek+xhgEl199TY0h9QP2F5Lt ZBXjr0rtH8aRPQhpGlCS28oTcXmO/J8/4svxdNXt37+rR/GynJBS -----END RSA PRIVATE KEY-----',
'-----BEGIN PUBLIC KEY----- MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAlD1rJejkgo7x8FgL43Pl fwtv0ulw9+dpCU0B4WljMpPADqW/HL4D8n4aS1cnEfXjOq+5F556nwGUeohJTFL0 li2SrFfwcB3MaCACO/3corNtfwaSKNyGErHhi56ReVYVWoWcXTkpJnW9kFNR19fM 9U2G3U50hc7NQgmJ5HElUHngjTUbEbuhyUMnxS1fR5Hh5l3b1rYiGoNGRzs3/j3j iq1akMKdy8z+rBjH/C8zzjN4WtzkNDb93NdcgH3iE7HyE0ydNoZ3RDAiTCMwlwib qN0EhzjCWZAEHajcVG9pKfagkxkiPCMz6ZdUtjZU+xghYH063DfuZ9MfT3mueBfn VwIDAQAB -----END PUBLIC KEY-----');

INSERT INTO stars (id, creator, text) VALUES ('fed11b63a5ac467b910af49a6826ed01', '247a1ca474b04a248c751d0eebf9738f', 'Hallo Welt!');