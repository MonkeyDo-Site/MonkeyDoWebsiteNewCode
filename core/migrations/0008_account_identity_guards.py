from django.db import migrations


def install(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Profile = apps.get_model("core", "AccountSecurity")
    for user_id in User.objects.values_list("pk", flat=True).iterator():
        Profile.objects.get_or_create(user_id=user_id)
    schema_editor.execute(
        "CREATE UNIQUE INDEX monkeydo_single_owner ON auth_user (is_superuser) WHERE is_superuser"
    )
    schema_editor.execute("CREATE UNIQUE INDEX monkeydo_username_ci ON auth_user (lower(username))")
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION monkeydo_username_immutable() RETURNS trigger AS $$
            BEGIN
                IF NEW.username IS DISTINCT FROM OLD.username THEN
                    RAISE EXCEPTION 'Usernames are permanent';
                END IF;
                RETURN NEW;
            END; $$ LANGUAGE plpgsql;
            CREATE TRIGGER monkeydo_username_guard BEFORE UPDATE OF username ON auth_user
            FOR EACH ROW EXECUTE FUNCTION monkeydo_username_immutable();
        """)
    elif schema_editor.connection.vendor == "sqlite":
        schema_editor.execute(
            "CREATE TRIGGER monkeydo_username_guard BEFORE UPDATE OF username ON auth_user WHEN NEW.username != OLD.username BEGIN SELECT RAISE(ABORT, 'Usernames are permanent'); END"
        )


def remove(apps, schema_editor):
    schema_editor.execute(
        "DROP TRIGGER monkeydo_username_guard"
        + (" ON auth_user" if schema_editor.connection.vendor == "postgresql" else "")
    )
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP FUNCTION monkeydo_username_immutable()")
    schema_editor.execute("DROP INDEX monkeydo_username_ci")
    schema_editor.execute("DROP INDEX monkeydo_single_owner")


class Migration(migrations.Migration):
    dependencies = [("core", "0007_securityrequestlimit_accountsecurity_ownerchallenge_and_more")]
    operations = [migrations.RunPython(install, remove)]
