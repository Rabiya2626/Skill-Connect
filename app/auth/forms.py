from flask_wtf import FlaskForm
from wtforms import BooleanField, EmailField, FileField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, URL, ValidationError

from app.models import User


class RegistrationForm(FlaskForm):
    name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    email = EmailField("Email address", validators=[DataRequired(), Email(), Length(max=255)])
    role = SelectField("I want to", choices=[("learner", "Learn skills"), ("tutor", "Teach skills"), ("both", "Do both")])
    bio = TextAreaField("Tell the community about yourself", validators=[Length(max=2000)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password", message="Passwords do not match.")])
    accept_terms = BooleanField("I accept the Terms of Service and Privacy Notice", validators=[DataRequired()])
    submit = SubmitField("Create my profile")

    def validate_email(self, email):
        if User.query.filter_by(email=email.data.lower()).first():
            raise ValidationError("An account already exists for this email address.")


class LoginForm(FlaskForm):
    email = EmailField("Email address", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")


class PasswordResetRequestForm(FlaskForm):
    email = EmailField("Email address", validators=[DataRequired(), Email()])
    submit = SubmitField("Send reset link")


class PasswordResetForm(FlaskForm):
    password = PasswordField("New password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField("Confirm new password", validators=[DataRequired(), EqualTo("password", message="Passwords do not match.")])
    submit = SubmitField("Reset password")


class ProfileForm(FlaskForm):
    name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    bio = TextAreaField("About you", validators=[Length(max=2000)])
    profile_picture = FileField("Profile photo", validators=[Optional()])
    portfolio_url = StringField("Portfolio URL", validators=[Optional(), URL(require_tld=False), Length(max=500)])
    certificate_url = StringField("Certificate URL", validators=[Optional(), URL(require_tld=False), Length(max=500)])
    learning_goals = TextAreaField("Learning goals", validators=[Length(max=2000)])
    submit = SubmitField("Save profile")
