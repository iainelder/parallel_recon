import boto3
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass
from awscli.customizations.configure.writer import ConfigFileWriter
from awscli.customizations.configure import profile_to_section


@dataclass
class OrgAccount(object):

    Id: str
    Arn: str
    Email: str
    Name: str
    Status: str
    JoinedMethod: str
    JoinedTimestamp: datetime


class Profile(object):
    pass


@dataclass
class ManagementProfile(Profile):

    account: OrgAccount
    session: boto3.session.Session


    def cli_config(self) -> Dict:
        config = self.session._session.get_scoped_config()
        config["__section__"] = profile_to_section("mgmt")
        return {
            k: v
            for k, v in config.items()
            if k not in [
                "aws_access_key_id",
                "aws_secret_access_key",
                "aws_session_token"
            ]
        }


@dataclass
class MemberProfile(Profile):
    
    account: OrgAccount


    def cli_config(self) -> Dict:
        return {
            "__section__": profile_to_section(self.account.Id),
            "source_profile": "mgmt",
            "role_arn": f"arn:aws:iam::{self.account.Id}:role/OrganizationAccountAccessRole"
        }

@dataclass
class ProfileWriter(object):

    config_path: str


    def write_profile(self, profile: Profile) -> None:
        ConfigFileWriter().update_config(profile.cli_config(), self.config_path)


    def write_profiles(self, profiles: List[Profile]) -> None:
        for profile in profiles:
            self.write_profile(profile)


@dataclass
class OrgConfigWriter(object):

    session: boto3.session.Session


    def get_active_accounts(self):

        all_accounts = self.session.client("organizations").list_accounts()["Accounts"]
        return (OrgAccount(**ac) for ac in all_accounts if ac["Status"] == "ACTIVE")
    

    def get_active_profiles(self):

        mgmt_id = self.management_account_id()
        active_accounts = self.get_active_accounts()
        return (
            ManagementProfile(ac, self.session) if ac.Id == mgmt_id else MemberProfile(ac)
            for ac in active_accounts
        )


    def management_account_id(self):

        return (
            self.session.client("organizations")
            .describe_organization()["Organization"]["MasterAccountId"]
        )


    def write_org_profiles(self):
        profiles = self.get_active_profiles()
        ProfileWriter(config_path="/tmp/profiles").write_profiles(profiles)
