import { PageHeader } from "@/components/page-header";

export const metadata = {
  title: "Privacy Policy | Peach",
  description: "How Peach handles basic account information.",
};

export default function PrivacyPage() {
  return (
    <article className="grid max-w-prose gap-8">
      <PageHeader
        title="Privacy Policy"
        description="Peach is a student/demo application. This policy describes how account information is handled when authentication is enabled."
      />

      <div className="grid gap-6 text-sm leading-7 text-muted-foreground [&_h2]:mb-2 [&_h2]:font-heading [&_h2]:text-base [&_h2]:font-semibold [&_h2]:text-foreground">
        <section>
          <h2>Authentication and account information</h2>
          <p>
            Peach uses authentication to identify users of the application. When
            you sign in with Google, Google may provide basic account
            information such as your name, email address, and profile
            information. Email and password sign-in may also use your email
            address to identify your account.
          </p>
        </section>

        <section>
          <h2>How account information is used</h2>
          <p>
            Basic account information is used only for authentication and
            account identification within Peach, including displaying your
            signed-in account. It is not used for advertising or sold to third
            parties. Authentication providers process information needed to
            complete sign-in under their own privacy policies.
          </p>
        </section>

        <section>
          <h2>Google permissions</h2>
          <p>
            Peach does not request access to Gmail, Google Drive, Google
            Calendar, or other unrelated Google services. Google sign-in is used
            only to authenticate you and identify your account.
          </p>
        </section>

        <section>
          <h2>Demo data and security</h2>
          <p>
            Peach is an educational demo. Avoid submitting sensitive personal
            information in task names, descriptions, or other demo content.
            Hosting and authentication services may process technical
            information needed to operate the application, such as request logs
            and session data.
          </p>
        </section>

        <section>
          <h2>Your choices and contact</h2>
          <p>
            You can choose not to sign in with Google and can revoke access
            through your Google account settings. For privacy questions or
            requests about account information, contact the Peach project
            maintainer through the project repository or the course channel
            through which this demo was shared.
          </p>
        </section>

        <section>
          <h2>Policy updates</h2>
          <p>
            This policy may be updated as the demo develops. Changes will be
            published on this page.
          </p>
        </section>
      </div>
    </article>
  );
}
