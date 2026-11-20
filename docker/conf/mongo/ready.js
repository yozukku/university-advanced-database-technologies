const hello = db.adminCommand({ hello: 1 });

if (hello.isreplicaset) {
    const initialized = rs.initiate({ _id: "rs0", members: [{ _id: 0, host: "mongo:27017" }] });
    if (initialized.ok !== 1) {
        printjson(initialized);
    }
    quit(1);
}

if (!hello.isWritablePrimary) {
    quit(1);
}

const defaults = db.adminCommand({ getDefaultRWConcern: 1 });
if (defaults.ok !== 1) {
    quit(1);
}

if (defaults.defaultWriteConcern?.w !== 1 || defaults.defaultWriteConcern?.j !== true) {
    const changed = db.adminCommand({
        setDefaultRWConcern: 1,
        defaultWriteConcern: { w: 1, j: true },
    });
    quit(changed.ok === 1 ? 0 : 1);
}
