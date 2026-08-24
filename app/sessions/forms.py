from flask_wtf import FlaskForm
from wtforms import IntegerField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, NumberRange, Optional

class FeedbackForm(FlaskForm):
    rating_value = IntegerField("Rating", validators=[DataRequired(), NumberRange(min=1, max=5)])
    comment = TextAreaField("Feedback", validators=[Optional()])
    submit = SubmitField("Submit feedback")
