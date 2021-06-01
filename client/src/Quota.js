import React from 'react';
import { TextField, Grid } from '@material-ui/core';

class QuotaParameter extends React.Component {

    constructor(props) {
        super(props);

        this.state = {
            name: this.props.parameter["name"],
            units: (this.props.parameter["units"] === '' ? '' : '(' + this.props.parameter["units"] + ')'),
            regex: new RegExp(this.props.parameter["regex"]),
            regex_description: this.props.parameter["regex_description"],

            value: this.props.current
        };

        this.validate = this.validate.bind(this)
    };

    validate(event) {
 
        // test input with regex
        if (event.target.value === '' || this.state.regex.test(event.target.value)) {

            // set field text
            this.setState({
                value: event.target.value
            })

            // edit quota object
            this.props.edit(this.props.parameter_name, event.target.value)
        }

    }

    render() {
        return (
            <TextField
                id={this.props.parameter_name}
                name={this.props.parameter_name}
                label={this.state.name + " " + this.state.units}
                helperText={this.state.regex_description}
                value={this.state.value}
                onChange={event => this.validate(event)}
                style={{ marginTop: '4%' }}
                fullWidth
            />
        )
    }

}

class ResourceQuota extends React.Component {

    constructor(props) {
        super(props);

        this.state = {
            quota: JSON.parse(JSON.stringify(this.props.current))
        };

        this.edit = this.edit.bind(this)
    };

    edit(name, value) {

        let quota = this.state.quota

        // if empty - remove from quota
        if (value === '') {
            delete quota[name]
        } else {
            quota[name] = value
        }

        this.setState({
            quota: quota
        })

        this.props.edit(this.props.name, quota)
    }

    render() {

        return Object.keys(this.props.fields).map(parameter_name =>
            <QuotaParameter
                parameter_name={parameter_name}
                parameter={this.props.fields[parameter_name]}
                edit={this.edit}
                current={this.props.current[parameter_name]}></QuotaParameter>
        )
        
    }

}

class Quota extends React.Component {

    constructor(props) {
        super(props);

        this.state = {
            quota: JSON.parse(JSON.stringify(this.props.current)),
            filled: true
        };

        this.edit = this.edit.bind(this)
    };

    edit(name, value) {

        let quota = this.state.quota

		// if not all keys are set - remove from final output
        if (Object.keys(value).length === Object.keys(this.props.scheme[name]).length) {
            quota[name] = value
        } else {
            delete quota[name]
        }

        this.setState({
            quota: quota,
        })

        let filled = (Object.keys(quota).length === Object.keys(this.props.scheme).length ? true : false)
        this.props.handleChange(quota, filled)
    }

    render() {

        return Object.keys(this.props.scheme).map(quota_object_name =>
            <Grid item xs={12 / Object.keys(this.props.scheme).length}>
                <ResourceQuota
                    name={quota_object_name}
                    fields={this.props.scheme[quota_object_name]}
                    edit={this.edit}
                    current={this.props.current[quota_object_name]}></ResourceQuota>
            </Grid>
        )

    }
}

export default Quota;